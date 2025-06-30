一个使用`esp32`控制`argb`风扇的Docker镜像，通过usb进行通信，使用webui界面设置风扇的灯光。

- DockerHub：https://hub.docker.com/r/sqing33/argb-fan-esp32
- Github：https://github.com/sqing33/docker-argb-fan-esp32
- CSDN：https://blog.csdn.net/qq_31800065/article/details/149028921?fromshare=blogdetail&sharetype=blogdetail&sharerId=149028921&sharerefer=PC&sharesource=qq_31800065&sharefrom=from_link

### 1. 使用方法：

- 修改esp32端ardunio代码为argb的data引脚，然后编译写入esp32，插入usb口
![image](https://github.com/user-attachments/assets/bfdb71e2-6714-4fbe-9e7a-3a92d15750ff)

- 修改docker-compose中`environment`的设备端口和`devices`挂载的usb设备


```yaml
services:
  argb-fan-esp32:
    image: sqing33/argb-fan-esp32  # ghcr.io/sqing33/argb-fan-esp32
    container_name: argb-fan-esp32
    restart: always
    ports:
      - 3232:3232
    environment:
      - COM_PORT=/dev/ttyUSB0
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    volumes:
      - /vol1/1000/Docker/argb-fan-esp32:/app/config
      - /etc/localtime:/etc/localtime:ro
    group_add:
      - "dialout"
```

### 2. 截图

![image](https://github.com/user-attachments/assets/ea3fe5dd-4848-45e5-854c-5cdeb13e0a17)
![image](https://github.com/user-attachments/assets/0f6cf375-525e-4696-a16c-6fb2454033c3)
