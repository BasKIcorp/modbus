import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import serial

PORT = 'COM6'


def main():
    """main"""
    logger = modbus_tk.utils.create_logger(name="console", record_format="%(message)s")

    # Create the server
    server = modbus_rtu.RtuServer(serial.Serial(port=PORT, baudrate=115200, parity='N', stopbits=2))

    try:
        logger.info("running...")

        server.start()

        slave_1 = server.add_slave(1)
        slave_1.add_block('first', cst.HOLDING_REGISTERS, 0x0001, 1)
        slave_1.add_block('second', cst.HOLDING_REGISTERS, 0x0002, 1)
        slave_1.add_block('fifth', cst.HOLDING_REGISTERS, 0x0005, 1)
        slave_1.add_block('sixth', cst.HOLDING_REGISTERS, 0x0006, 1)

        slave = server.get_slave(1)
        slave.set_values('first', 1, 19)
        slave.set_values('second', 2, 4)
        slave.set_values('fifth', 5, 0)
        slave.set_values('sixth', 6, 12)
    except:
        logger.info("error")


if __name__ == "__main__":
    main()
