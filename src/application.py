# === Imports ===
import argparse             # Command-line argument parsing
from socket import *        # UDP sockets
from struct import *        # Binary header packing/unpacking
import sys                  # System exit
import ipaddress            # IPv4 validation
import time                 # Timing transfers / timeouts
from datetime import datetime  # Timestamped log messages
import os                   # File operations (size, rename)

# === Packet layout constants ===
header_format = '!HHH'       # Network byte order: seq (2B), ack (2B), flags (2B)
packet_data_size = 994       # Data bytes per packet (1000 - 6 header bytes)

# === Flag bitmasks ===
syn_flag = 0b1000
ack_flag = 0b0100
fin_flag = 0b0010

timeout = 0.500  # Client timeout in seconds

# === Utility functions ===
def split_file(file_path):
    """
    Read a file and yield successive 994-byte chunks.

    :param file_path: Path to file in binary mode
    :yield: Bytes object of max length 994
    """
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(packet_data_size)
            if not chunk:
                break
            yield chunk

def throughput(start, end, data_bytes):
    """
    Compute throughput in Mbps.
    
    :param start: Transfer start time (seconds)
    :param end: Transfer end time (seconds)
    :param data_bytes: Total data size in bytes
    :return: Throughput as string formatted 'xx.xx'
    """
    time_taken = end - start
    mbps = (data_bytes * 8 / 1_000_000) / time_taken
    return f"{mbps:.2f}"

def pack_header(seq, ack, flags):
    """Pack header into 6 bytes (seq, ack, flags)."""
    return pack(header_format, seq, ack, flags)

def unpack_header(header_bytes):
    """Unpack a 6-byte header into (seq, ack, flags)."""
    return unpack(header_format, header_bytes)

def send_ack_packet(sock, address, seq, ack):
    """
    Send an ACK packet to `address` acknowledging `seq`.
    """
    sock.sendto(pack_header(seq, ack, ack_flag), address)
    time_string = datetime.now().strftime("%H:%M:%S.%f")
    print(f"{time_string} -- sending ACK for packet seq={seq}")

def check_ip(ip):
    """
    Validate IPv4 address. Exit on error.
    """
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        print("Invalid IP. Format example: 127.0.0.1")
        sys.exit()
    return True

def check_port(port):
    """
    Validate port in [1024,65535]. Exit on error.
    """
    if int(port) < 1024 or int(port) > 65535:
        print("Invalid port. Must be in range [1024,65535]")
        sys.exit()
    return True

# === Server ===
def receive_file(ip, port, discard):
    """
    Run the server: receive packets over DRTP/UDP and write to a file.

    :param ip: Server IP address
    :param port: Port number
    :param discard: Sequence number to discard for testing
    """
    server_socket = socket(AF_INET, SOCK_DGRAM)  # UDP socket
    try:
        server_socket.bind((ip, port))
    except OSError as e:
        print(f"{e}\nThe given IP/port is not available. "
              "Try 127.0.0.1:8080 or (10.0.1.2) in Mininet.")
        sys.exit()

    # Wait for initial SYN
    syn_packet, client_address = server_socket.recvfrom(6)
    server_socket.settimeout(5)  # Timeout for client inactivity

    _, _, flags = unpack_header(syn_packet)

    if flags & syn_flag:
        print("SYN packet is received")
        syn_ack_packet = pack_header(0, 0, syn_flag | ack_flag)
        server_socket.sendto(syn_ack_packet, client_address)
        print("SYN-ACK packet is sent")

        # Wait for ACK
        ack_packet, _ = server_socket.recvfrom(6)
        _, _, flags = unpack_header(ack_packet)

        if flags & ack_flag:
            print("ACK packet is received\n\nConnection Established\n")

            with open("new_file", "wb") as new_file:
                ack = 1
                time_start = time.time()

                while True:
                    packet, _ = server_socket.recvfrom(1000)
                    seq, _, flags = unpack_header(packet[:6])

                    # Discard test packet once
                    if seq == discard:
                        discard = float('inf')
                        continue

                    # Check for FIN
                    if flags & fin_flag:
                        print("\nFIN packet is received\nData transfer finished")
                        break

                    # Packet with seq==1 contains file name
                    if seq == 1:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(f"{time_string} -- packet seq={seq} is received")
                        file_name = packet[6:].decode()
                        send_ack_packet(server_socket, client_address, seq, ack)
                        ack += 1
                        continue
                    
                    # In-order packet
                    if seq == ack:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(f"{time_string} -- packet seq={seq} is received")
                        send_ack_packet(server_socket, client_address, seq, ack)
                        new_file.write(packet[6:])
                        ack += 1
                    else:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(f"{time_string} -- out-of-order packet seq={seq} received")

                time_end = time.time()

            # Send FIN-ACK
            fin_ack_packet = pack_header(0, 0, fin_flag | ack_flag)
            server_socket.sendto(fin_ack_packet, client_address)
            print("FIN-ACK packet is sent\n")

            # Rename file with proper extension, handle duplicates
            if os.path.exists(file_name):
                file_extension = file_name.split(".")[-1]
                file_base = "".join(file_name.split(".")[:-1])
                copy = 0
                while os.path.exists(f"{file_base}({copy}).{file_extension}"):
                    copy += 1
                final_file = f"{file_base}({copy}).{file_extension}"
                os.rename("new_file", final_file)
            else:
                final_file = file_name
                os.rename("new_file", file_name)

            # Throughput calculation
            network_throughput = throughput(time_start, time_end, os.path.getsize(final_file))
            print(f"The throughput is {network_throughput} mbps\n")
            print("Connection Closes")
            server_socket.close()

# === Client ===
def send_file(ip, port, file, window):
    """
    Run the client: send file packets over DRTP/UDP.

    :param ip: Server IP address
    :param port: Server port
    :param file: File path to send
    :param window: Sliding window size
    """
    client_socket = socket(AF_INET, SOCK_DGRAM)
    server_address = (ip, port)
    client_socket.settimeout(timeout)
    print("Connection Establishment Phase:\n")

    try:
        client_socket.sendto(pack_header(0, 0, syn_flag), server_address)
        print("SYN packet is sent")
        syn_ack_packet, _ = client_socket.recvfrom(6)
        _, _, flags = unpack_header(syn_ack_packet)

    except ConnectionResetError:
        print("\n...\n\nCould not connect to the server")
        print("Check if the server is running or if IP/port is correct")
        client_socket.close()
        sys.exit()

    except TimeoutError:
        print("\n...\n\nThe server did not respond with a SYN-ACK.")
        client_socket.close()
        sys.exit()

    if flags & syn_flag and flags & ack_flag:
        print("SYN-ACK packet is received")
        client_socket.sendto(pack_header(0, 0, ack_flag), server_address)
        print("ACK packet is sent\n\nConnection established\n")

        seq = 1
        window_size = []
        packet_dict = {}
        last_loop = os.path.getsize(file) // 994 + (1 if os.path.getsize(file) % 994 else 0)

        print("Data Transfer:\n")

        # Send file name first
        file_name = os.path.basename(args.file)
        client_socket.sendto(pack_header(seq, 0, ack_flag)+file_name.encode(), server_address)
        packet_dict[seq] = pack_header(seq, 0, ack_flag)+file_name.encode()
        window_size.append(seq)
        time_string = datetime.now().strftime("%H:%M:%S.%f")
        print(f"{time_string} -- packet seq={seq} sent, sliding window={window_size}")
        seq += 1

        for data_chunk in split_file(file):
            if len(window_size) < window:
                window_size.append(seq)

            packet = pack_header(seq, 0, ack_flag) + data_chunk
            packet_dict[seq] = packet
            client_socket.sendto(packet, server_address)
            time_string = datetime.now().strftime("%H:%M:%S.%f")
            print(f"{time_string} -- packet seq={seq} sent, sliding window={window_size}")

            while len(window_size) == window or seq-1 == last_loop and len(window_size) != 0:
                try:
                    client_socket.settimeout(timeout)
                    ack_packet, _ = client_socket.recvfrom(6)
                    server_seq, ack, flags = unpack_header(ack_packet)
                    if flags & ack_flag:
                        if server_seq == ack == window_size[0]:
                            time_string = datetime.now().strftime("%H:%M:%S.%f")
                            print(f"{time_string} -- ACK for packet seq={ack} is received")
                            packet_dict.pop(window_size[0])
                            window_size = window_size[1:]
                        else:
                            raise ValueError 
                
                except ConnectionResetError:
                    print("\n...\n\nLost contact with the server, terminating")
                    client_socket.close()
                    sys.exit()

                except (TimeoutError, ValueError):
                    time_string = datetime.now().strftime("%H:%M:%S.%f")
                    print(f"{time_string} -- RTO occurred")
                    for key in window_size:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(f"{time_string} -- retransmitting lost packet seq={key}")
                        discarded_packet = packet_dict[key]
                        client_socket.sendto(discarded_packet, server_address)

            seq += 1
        
        print("\nData transfer finished\n")
        print("Connection Teardown:\n")

        while True:
            client_socket.sendto(pack_header(0, 0, fin_flag), server_address)
            print("FIN packet is sent")
            try:
                fin_ack_packet, _ = client_socket.recvfrom(6)
            except TimeoutError:
                print("\n...\n\nNo FIN-ACK received, resending FIN packet...")
                continue

            _, _, flags = unpack_header(fin_ack_packet)
            if flags & fin_flag and flags & ack_flag:
                break

        print("FIN-ACK packet is received\n\nConnection Closes")
        client_socket.close()

# === Argument parsing ===
parser = argparse.ArgumentParser(description='Run server or client to receive/send a file to the specified IP and port')
parser.add_argument('-s', '--server', action='store_true', help='Enable server mode')
parser.add_argument('-c', '--client', action='store_true', help='Enable client mode')
parser.add_argument('-i', '--ip', type=str, default='127.0.0.1', help='IPv4 address (default 127.0.0.1)')
parser.add_argument('-p', '--port', type=int, default=8080, help='Port [1024,65535] (default 8080)')
parser.add_argument('-f', '--file', type=str, help='File path to send (client mode)')
parser.add_argument('-w', '--window', type=int, default=3, help='Sliding window size (default 3)')
parser.add_argument('-d', '--discard', type=int, default=float('inf'), help='For testing: discard this packet number')
args = parser.parse_args()

check_ip(args.ip)
check_port(args.port)

if args.server and args.client:
    print("You cannot enable both the server and the client at the same time")
elif args.server:
    receive_file(args.ip, args.port, args.discard)
elif args.client:
    try:
        if not args.file:
            print("A file path must be provided (use -f). See -h for help.")
            sys.exit()
        elif os.path.getsize(args.file) > 60000000:
            print("File must be smaller than 60 MB.")
            sys.exit()
        elif args.window < 1:
            print("Sliding window size must be > 0.")
            sys.exit()

        send_file(args.ip, args.port, args.file, args.window)
    except FileNotFoundError:
        print("File not found. Please provide a valid file path.")
        sys.exit()
else:
    print("Enable either server (-s) or client (-c). See -h for help.")
