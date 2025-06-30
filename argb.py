from flask import Flask, request, send_from_directory, jsonify
import serial
import threading
import time
from datetime import datetime
import os
import json

app = Flask(__name__, static_folder='.')

# --- 配置 ---
COM_PORT_ENV = os.getenv('COM_PORT', '/dev/ttyUSB0')
BAUD_RATE = 115200
CONFIG_DIR = 'config'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'last_state.json')

# --- 全局变量 ---
ser = None
ser_lock = threading.Lock()
current_port = None
# 用于定时任务的全局变量
schedule_enabled = True
schedule_start = "00:00"
schedule_end = "08:00"
scheduler_turned_off_light = False  # 标记是否由调度器关闭了灯
# 用于优雅地停止线程的事件
stop_scheduler_event = threading.Event()


def save_state_to_config(state_data):
    """将指定的状态数据保存到配置文件中。"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
    except Exception as e:
        print(f"  [警告] 无法写入配置文件: {e}")


def load_state_from_config():
    """从配置文件读取完整的状态。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def send_light_command(command_data, save_state=True):
    """
    发送指令到ESP32的统一函数。
    :param command_data: 要发送的JSON对象 (例如 {'mode':'static', 'color':'#ff0000'})
    :param save_state: 是否将此状态保存为“用户最后设置的状态”
    """
    if not ser or not ser.is_open:
        print(f"  [警告] 发送指令失败：串口未连接。")
        return False

    json_str = json.dumps(command_data) + '\n'
    try:
        with ser_lock:
            ser.write(json_str.encode('utf-8'))

        if save_state:
            # 只保存灯光状态，不保存定时计划
            full_config = load_state_from_config()
            full_config['light_state'] = command_data
            save_state_to_config(full_config)

        return True
    except Exception as e:
        print(f"  [错误] 指令发送时发生异常: {e}")
        return False


def scheduler_thread():
    """在后台运行的线程，用于检查是否需要开关灯。"""
    global scheduler_turned_off_light
    print("  ⏰ 定时任务线程已启动。")
    while not stop_scheduler_event.is_set():
        if not schedule_enabled:
            stop_scheduler_event.wait(60)  # 如果禁用，则等待60秒
            continue

        try:
            now = datetime.now().time()
            start = datetime.strptime(schedule_start, "%H:%M").time()
            end = datetime.strptime(schedule_end, "%H:%M").time()

            is_off_time = False
            if start <= end:  # 非跨天情况 (e.g., 00:00-08:00)
                if start <= now < end:
                    is_off_time = True
            else:  # 跨天情况 (e.g., 22:00-06:00)
                if now >= start or now < end:
                    is_off_time = True

            if is_off_time and not scheduler_turned_off_light:
                print(f"  [定时任务] 当前时间 {now.strftime('%H:%M')} 在关闭时段内，关闭灯光。")
                send_light_command({
                    'mode': 'static',
                    'color': '#000000'
                },
                                   save_state=False)
                scheduler_turned_off_light = True

            elif not is_off_time and scheduler_turned_off_light:
                print(f"  [定时任务] 当前时间 {now.strftime('%H:%M')} 在开启时段内，恢复灯光。")
                config = load_state_from_config()
                last_light_state = config.get('light_state')
                if last_light_state:
                    send_light_command(last_light_state, save_state=False)
                scheduler_turned_off_light = False

        except Exception as e:
            print(f"  [错误] 定时任务线程发生异常: {e}")

        stop_scheduler_event.wait(60)  # 每60秒检查一次
    print("  ⏰ 定时任务线程已停止。")


def connect_to_port(port):
    global ser, current_port
    if not port: return (False, "未提供端口号")
    try:
        with ser_lock:
            if ser and ser.is_open:
                ser.close()
                time.sleep(0.1)
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)
            current_port = port
        return (True, f"已连接到 {port}")
    except Exception as e:
        ser, current_port = None, None
        return (False, str(e))


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/config', methods=['GET'])
def api_get_config():
    with ser_lock:
        is_connected = ser.is_open if ser else False
        connected_port = current_port if is_connected else None
    config = load_state_from_config()
    return jsonify({
        'default_com_port':
        COM_PORT_ENV,
        'is_connected':
        is_connected,
        'connected_port':
        connected_port,
        'last_light_state':
        config.get('light_state'),
        'schedule':
        config.get('schedule', {
            'start_time': '00:00',
            'end_time': '08:00'
        })
    })


@app.route('/api/schedule', methods=['POST'])
def api_set_schedule():
    """接收并保存新的定时计划。"""
    global schedule_start, schedule_end
    data = request.get_json(force=True)
    schedule_start = data.get('start_time', '00:00')
    schedule_end = data.get('end_time', '08:00')

    full_config = load_state_from_config()
    full_config['schedule'] = {
        'start_time': schedule_start,
        'end_time': schedule_end
    }
    save_state_to_config(full_config)
    print(f"  [配置] 新的定时计划已保存: {schedule_start} - {schedule_end}")
    return jsonify({'success': True, 'msg': '计划已更新'})


@app.route('/api/connect', methods=['POST'])
def api_connect():
    port_to_connect = request.get_json(force=True).get('port')
    success, msg = connect_to_port(port_to_connect)
    if success: return jsonify({'success': True, 'msg': msg})
    else: return jsonify({'success': False, 'msg': msg}), 500


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    global ser, current_port
    try:
        with ser_lock:
            if ser and ser.is_open: ser.close()
            ser, current_port = None, None
        return jsonify({'success': True, 'msg': '已断开'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500


@app.route('/api/send', methods=['POST'])
def api_send():
    global scheduler_turned_off_light
    data = request.get_json(force=True)
    # 当用户手动设置颜色时，意味着定时任务的关闭状态应该被重置
    scheduler_turned_off_light = False
    if send_light_command(data, save_state=True):
        return jsonify({'success': True, 'msg': 'OK'})
    else:
        return jsonify({'success': False, 'msg': '指令发送失败'}), 500


if __name__ == '__main__':
    # 1. 从配置文件加载状态
    config = load_state_from_config()
    schedule_config = config.get('schedule', {})
    schedule_start = schedule_config.get('start_time', "00:00")
    schedule_end = schedule_config.get('end_time', "08:00")

    # 2. 启动后台定时任务线程
    scheduler = threading.Thread(target=scheduler_thread, daemon=True)
    scheduler.start()

    # 3. 自动连接串口
    print("--- 服务器启动 ---")
    print(f"正在尝试自动连接到端口: {COM_PORT_ENV}...")
    success, msg = connect_to_port(COM_PORT_ENV)

    if success:
        print(f"✅ 自动连接成功: {msg}")
        # 4. 如果连接成功，则尝试还原上次的灯光状态
        last_light_state = config.get('light_state')
        if last_light_state:
            print("  正在还原上次的灯光状态...")
            send_light_command(last_light_state, save_state=False)
    else:
        print(f"❌ 自动连接失败: {msg}")

    print("\n----------------------------------------------------")
    print(f"请在浏览器中打开 http://<您的IP地址>:3232")
    print("----------------------------------------------------")
    app.run(host='0.0.0.0', port=3232)
