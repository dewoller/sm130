import logging
import serial
import struct
import sys
import time


def sm130_checksum(packet):
  return sum(ord(x) for x in packet) % 256


def build_packet(command, payload):
  packet = struct.pack('BBB', 0x00, len(payload) + 1, command)
  packet += payload
  packet = '\xff' + packet + struct.pack('B', sm130_checksum(packet))
  return packet


def send_command(s, command, payload):
  packet = build_packet(command, payload)
  s.write(packet)
  header, reserved, len, response_to = struct.unpack('BBBB', s.read(4))
  assert header == 0xFF
  assert reserved == 0x00
  response = s.read(len - 1)
  response_checksum = s.read(1)
  computed_checksum = build_packet(response_to, response)[-1]
  assert computed_checksum == response_checksum
  assert command == response_to
  return response


def read_image_data(f):
  # Discard the header
  f.readline()
  return [x.strip().decode('hex') for x in f.readlines()]


def flash(s, image):
  logging.info("Enabling update mode.")
  s.write('\xff\x00\x01\x95\x96')
  assert s.read(6) == '\xff\x00\x02\x95\x00\xff'
  logging.info("Beginning update.")
  start_chunk = '\xff\x38\xaa\x55\x33\x68\x98\x0b'
  s.write(start_chunk)
  result = s.read(1)
  assert result == '\x20', result.encode('hex')
  for i, chunk in enumerate(image):
    s.write(chunk)
    result = s.read(1)
    assert result == '\x20', result.encode('hex')
    logging.info("Wrote chunk %d/%d.", i, len(image))
  logging.info("Finalizing update.")
  s.write('\xff\x3b\xaa\x55\x33\x68\x98\x0b'.ljust(0x4e, '\0'))
  result = s.read(1)
  assert result == '\x21', result.encode('hex')


def main(args):
  image = read_image_data(open(args[1]))
  if len(args) == 3:
    rate = 19200
  else:
    rate = args[3]
  s = serial.Serial(args[2], rate)
  # Give the module a chance to reset
  time.sleep(2)
  s.flushInput()
  logging.info("Version before update: %s", send_command(s, 0x81, ''))
  flash(s, image)
  time.sleep(2)
  logging.info("Version after update: %s", send_command(s, 0x81, ''))


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  main(sys.argv)
