#Importing argparse to enable argument parsing through the console
import argparse
#Importing socket to enable a basic network interface and file transfer through UDP
from socket import *
#Importing struct to create headers for DRTP
from struct import *
#Importing sys exclusively for the sys.exit command to terminate the program
import sys
#Importing ipaddress for use in the check_ip function, to be able to more easily check if the provided ip is a valid ipv4 address
import ipaddress
#Importing time for use in determining whether sent packages have been discarded or not
import time
#Importing datetime for assigning the computer's local time along with printed messages
from datetime import datetime
#Importing os to get the true size of the file
import os

#Full packets are 1000 bytes, comprised of the header (6 bytes) and the data (994 bytes)
#6 bytes header, as H = 2 bytes, each unsigned short can only be between 0 and 65535
header_format = '!HHH'
#Variable for the remaining 994 bytes
packet_data_size = 994

#Header variables, starts the seq number at 0 for the header-only packets
flags = 0

#Defining packet flags as variables
syn_flag = 0b1000
ack_flag = 0b0100
fin_flag = 0b0010

#Timeout specified as 0.500 seconds
timeout = 0.500

#Function to read a file and split it into multiple chunks of 994 bytes
#Parameter is a file provided through argparse arguments inputted by the user
def split_file(file):
    #Opens the file in binary mode
    with open(file, 'rb') as file:
        while True:
            #Assigns the next chunk (994 bytes) of the file to the data_chunk variable
            data_chunk = file.read(packet_data_size)
            #If the data_chunk variable is empty, then the loop has reached the end of the file, and thus breaks
            if not data_chunk:
                break
            #Returns the variable for usage outside of the function, aswell as saving the while loops progress for further reading of the file
            yield data_chunk

#Function for calculcating the network throughput
#Parameters are the start of the transfer process, the end of the transfer process and the total data size in bytes
def throughput(start, end, data):
    #A variable that determines the data transfer's total time taken in seconds
    time_taken = end - start
    #Calculating the throughput in megabits per second, so converting from bytes per second to megabits per second
    throughput_mbps = (data * 8 / 1000000)/time_taken
    #Returning the throughput in Mbps
    return "{:.2f}".format(throughput_mbps)

#Function to create and pack a header
#Parameters are seq (sequence number), ack (acknowledgement number) and flags
#Seq determines the packet's id, ack determines the whether the server has acknowledged it and flags determines the SYN, ACK and FIN flags used in the TCP three-way handshake
def pack_header(seq, ack, flags):
    #Creates and returns a header variable for use in packets. Will always be placed in the 6 first bytes as the header format is !HHH where H is 2 bytes each
    header = pack(header_format, seq, ack, flags)
    return header

#Function to unpack a header
#Parameter is a packet, either sent by the client, or the server.
def unpack_header(header_package):
    #Unpacks and returns the sequence number, acknowledgement number and flags from a packed header
    return unpack(header_format, header_package)

#Function that sends an ack packet to a specific address
#Parameters are socket: The socket that is sending the packet, address: The ip/port address that the packet is being sent to
#seq: The packet's sequence number, and ack: The packet's acknowledgement number
def send_ack_packet(socket, address, seq, ack):
    #Sends an ACK packet to the ip:port address to acknowledge that the packet was received
    socket.sendto(pack_header(seq, ack, ack_flag), address)
    #A string variable that saves the local time, needs to be reassigned every time it is used
    time_string = datetime.now().strftime("%H:%M:%S.%f")
    print(time_string+" -- sending ACK for the received packet with seq number = "+str(seq))  

#Function to check if the ip is a valid ip
def check_ip(ip):
    #Uses exception handling because ipaddress.ip_address(ip) raises a ValueError if the target isn't a valid ip
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        print("Invalid IP. It must be in this format: 127.0.0.1")
        sys.exit()
    #Returns true if an exception isn't catched to acknowledge that the ip is valid
    return True

#Function to check if the port is a valid port
def check_port(port):
    #Basic if-statement to see if the port is within the range [1024,65535]
    if int(port) < 1024 or int(port) > 65535:
        print("Invalid port. It must be within the range [1024,65535]")
        sys.exit()
    #Returns true to acknowledge that it is a valid port
    return True

#Function that serves as the server, receives packets over DRTP/UDP and writes the data content to a new file
#Parameters are the argparse arguments ip for ip address, port for port address and discard for discarding a packet with the selected sequence number
def receive_file(ip, port, discard):
    server_socket = socket(AF_INET, SOCK_DGRAM) #Starting a UDP (SOCK_DGRAM) server socket, awaiting a connection over IPV4 (AF_INET)
    try:
        server_socket.bind((ip, port)) #Binds the server socket to the given ip and port
    except OSError as e:
        print(str(e)+"\nThe given IP and port combination is not available on your local machine, ensure that the combination is accessible, or try to use the default ip (127.0.0.1) and port (8080) provided\nIf using mininet through simple-topo.py, use the server ip: (10.0.1.2) on h2")
        sys.exit()
    #Waits for and receives a SYN packet (6 bytes) from the client address
    syn_packet, client_address = server_socket.recvfrom(6)
    server_socket.settimeout(5) #Sets a timeout value to the server socket that raises a TimeoutError if the client stops responding, using 5 seconds in this case to give the client ample time to respond

    #Unpacking the SYN packet into three variables, seq and ack are unneeded
    _, _, flags = unpack_header(syn_packet)

    #If the received packets flags matches the syn_flag ('0b1000', or 8 in decimal)
    if flags & syn_flag:
        print("SYN packet is received")
        #Sending a SYN-ACK packet to the client address, seq and ack = 0 because it only contains a header
        syn_ack_packet = pack_header(0, 0, syn_flag | ack_flag) #syn_flag | ack_flag assigns and combines both of the flags to the header ('0b1100', or 12 in decimal)
        server_socket.sendto(syn_ack_packet, client_address) 
        print("SYN-ACK packet is sent")

        #Receiving an ACK packet (6 bytes) from the client address, re-assigning the client address to a variable is unneeded, hence _.
        ack_packet, _ = server_socket.recvfrom(6)
        #Unpacking the ACK packet into three variables, seq and ack are unneeded
        _, _, flags = unpack_header(ack_packet)

        #If statement that checks if the header's flags value is the same as an ack flag ('0b0100', or 4 in decimal)
        if flags & ack_flag:
            print("ACK packet is received\n\nConnection Established\n")

            with open("new_file", "wb") as new_file:
                #Assigning the acknowledgement number to 1 for use in the data transfer process
                ack = 1
                #A variable for determining when the transfer starts, for use in the throughput function
                time_start = time.time()

                while True:
                    #Receiving a packet (1000 bytes, 6 from the header, 994 from the data chunk) from the client address, reassigning the address is unneeded
                    packet, _ = server_socket.recvfrom(1000)
                    #Unpacking the header (first 6 bytes) from the packet, seq is needed to check if the packets haven been received in order, 
                    #flags are needed to check for a FIN flag in case the data transfer process is complete
                    seq, _, flags = unpack_header(packet[:6])
                    
                    #If statement for testing discarded packets, if the current packet's sequence number is the same as the packet set to be discarded, then it skips the current loop, effectively discarding the packet
                    if seq == discard:
                        #Sets discard to an infinitely high number, as it is only supposed to discard once
                        discard = float('inf')
                        #Skips the current loop
                        continue

                    #If statement that checks if the unpacked flags value is the same as a FIN flag ('0b0010', or 2 in decimal), breaks the loop if so
                    if flags & fin_flag:
                        print("\nFIN packet is received\nData transfer finished")
                        break

                    #If the sequence number is 1, then the received packet includes the file extension
                    if seq == 1:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(time_string + " -- packet with seq number = "+str(seq)+" is received")
                        #Decodes the file extension contained in the packet's data and assigns it to a variable
                        file_name = packet[6:].decode()
                        #Sends an ACK packet to the client to acknowledge that the file extension was received
                        send_ack_packet(server_socket, client_address, seq, ack)
                        #Increases the acknowledge number for use in further packets, as each ACK packet needs its own unique ack number
                        ack += 1
                        #Starts an additional loop
                        continue
                    
                    #If statement that checks if the sequence- and the acknowledge number are the same, if so, no packet has been lost and it proceeds
                    #If this if statement fails, then it loops without sending another packet back to the client. The client will then resend the lost packets after a set amount of time
                    if seq == ack:
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(time_string + " -- packet with seq number = "+str(seq)+" is received")
                        #Initializes the send_ack_packet function to send an ACK packet back to the client
                        send_ack_packet(server_socket, client_address, seq, ack)
                        #Since the seq and ack is the same, it will write the data to the new file, and increase the ack for use in the next received packet
                        new_file.write(packet[6:])
                        ack += 1
                    else:
                        #Reassigns the local time to a variable for use in logging, needs to be reassigned each time it is used
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(time_string+" -- out-of-order packet "+str(seq)+" is received")
                        

                #A variable that determines the endpoint of the data transfer, for use in the throughput function
                time_end = time.time() 
            
            #Sending a FIN-ACK packet back to the client address, seq and ack are unneeded
            fin_ack_packet = pack_header(0, 0, fin_flag | ack_flag) #fin_flag | ack_flag assigns and combines both of the flags to the header ('0b0110' or 6 in decimal)
            server_socket.sendto(fin_ack_packet, client_address)
            print("FIN-ACK packet is sent\n")

            #If statement that checks if a file with the same name along with its file extension exists
            if os.path.exists(file_name):
                #Splits the filename and the extension into two variables
                file_extension = file_name.split(".")[-1]
                file_name = "".join(file_name.split(".")[:-1])
                #If there is a file with the same name already, initialize an int variable
                copy = 0
                #While loop that loops until a valid name is found for the new file
                while True:
                    if not os.path.exists(file_name+"("+str(copy)+")."+file_extension):
                        break
                    copy += 1
                #Adds a variable with the final filename, for use in the network throughput
                final_file = file_name+"("+str(copy)+")."+file_extension
                #Renames the new file to its proper extension without removing any previous files with the same name
                os.rename("new_file", file_name+"("+str(copy)+")."+file_extension)
            else:
                #Adds a variable with the final filename, for use in the network throughput
                final_file = file_name
                #Renames the new file to its proper extension without removing any previous files with the same name
                os.rename("new_file", file_name)
            
            #Calculates and prints out the network throughput
            network_throughput = throughput(time_start, time_end, os.path.getsize(final_file))
            print("The throughput is "+network_throughput+" mbps\n")
            print("Connection Closes")
            #Closes the server socket to disconnect the server
            server_socket.close()

#Function that serves as a client, sends files in the form of packets over DRTP/UDP, requires argparse arguments
#Parameters are the argparse arguments ip, for ip address, port for port address, file for the full path to a file, and window for the size of the sliding window
def send_file(ip, port, file, window):
    client_socket = socket(AF_INET, SOCK_DGRAM) #Starting a UDP (SOCK_DGRAM) client socket, can be used to send packets over IPV4 (AF_INET)
    server_address = (ip, port) #Assigns the server address to a variable through the given ip and port
    client_socket.settimeout(timeout) #Assigns a timeout value to the client socket, raising a specified timeout error if it occurs
    print("Connection Establishment Phase:\n")

    #Error handling in case the server is offline, or if the IP and/or port specified is wrong
    try:
        #Sending a SYN packet to initiate a three-way handshake and to establish connection, seq and ack == 0, while the flags is set to be the same as a syn flag ('0b1000', or 8 in decimal)
        client_socket.sendto(pack_header(0, 0, syn_flag), server_address)
        print("SYN packet is sent")
        #Receiving a 6-byte SYN-ACK packet from the server, acknowledging the connection initiation. Reassigning the server address is unneeded hence the _
        syn_ack_packet, _ = client_socket.recvfrom(6)
        #Unpacking the header, seq and ack is unneeded
        _, _, flags = unpack_header(syn_ack_packet)
    
    #If a ConnectionResetError is catched, then either the server is offline, or the IP/Port is not correct
    except ConnectionResetError:
        print("\n...\n\nCould not connect to the server")
        print("Check if the server is running, or if the specified IP and port is correct")
        client_socket.close() #Closes the socket
        sys.exit() #Terminate the client

    #If a TimeoutError is catched, then the client never got a SYN-ACK packet, as the server stopped responding
    except TimeoutError:
        print("\n...\n\nThe server did not respond, a SYN-ACK packet was not received.\nRecheck the IP and port, and re-establish the connection to the server")
        client_socket.close() #Closes the socket
        sys.exit() #Terminate the client

    #If statement that checks if the flags variable is bitwise equal to both a syn flag and an ack flag ('0b1100', or 12 in decimal)
    if flags & syn_flag and flags & ack_flag:
        print("SYN-ACK packet is received")
        #Sending an ACK packet to the server to acknowledge and confirm the established connection, and start the data transfer.
        #seq and ack = 0 because the packet is a header
        client_socket.sendto(pack_header(0, 0, ack_flag), server_address)
        print("ACK packet is sent\n\nConnection established\n")

        #Setting seq to 1 to determine the first packet
        seq = 1
        #Creating an empty list for the sliding window
        window_size = []
        #Creating an empty dictionary to temporarily save the packets' data along with the seq numbers stored in the sliding window
        packet_dict = {}
        #Saving the last possible loop to a variable by dividing the size of the file with the chunk size (1000 - header = 994)
        #Also checks if the division is perfect, if not then it adds an additional loop
        last_loop = os.path.getsize(file) // 994 + (1 if os.path.getsize(file) % 994 else 0)
        
        print("Data Transfer:\n")

        #Before the data transfer takes place, the proper file extension is sent to the server to prevent it from having to guess the file extension
        #Adds the file extension from the argparse argument provided file to a variable
        file_name = os.path.basename(args.file)
        #Sends the file extension encoded as binary data to the server address, includes a header with only the sequence number and the encoded file extension
        #No packet variable used because this happens outside of the file transfer loop, and as such only happens once
        client_socket.sendto(pack_header(seq, 0, ack_flag)+file_name.encode(), server_address)
        #Adds the file extension along with its seq number to the dictionary and the packet's seq number to the sliding window list in case of the packet being lost
        packet_dict[seq] = pack_header(seq, 0, ack_flag)+file_name.encode() #encoded in binary
        window_size.append(seq)
        #Reassigns the local time to a variable for proper terminal logging
        time_string = datetime.now().strftime("%H:%M:%S.%f")
        print(time_string + " -- packet with seq number = "+str(seq)+" is sent, sliding window = "+str(window_size))        
        #Increases the seq number, as each packet has to have a unique sequence number
        seq += 1

        #For loop to start the data transfer process by splitting the file into multiple data chunks
        for data_chunk in split_file(file):
            #Appends the sequence number into the window size list if it contains less than the specified amount
            if len(window_size) < window:
                window_size.append(seq)
            #Combines the header and the data chunk into a packet. Assigned with the packet's sequence number
            packet = pack_header(seq, 0, ack_flag) + data_chunk
            #Adds the sequence number as a key and its packet as a value to a dictionary
            packet_dict[seq] = packet
            #Sends the packet to the server
            client_socket.sendto(packet, server_address)
            #Assigns the local time to a variable, a reassignment is needed each time it is used
            time_string = datetime.now().strftime("%H:%M:%S.%f")
            print(time_string + " -- packet with seq number = "+str(seq)+" is sent, sliding window = "+str(window_size))
            
            #A while loop that triggers if the sliding window is equal to the window size specified,
            #or if the window size still has packets after the for loop is finished.
            #'seq-1' is specified because the first sequence number is used to send the file extension, and not as a way to determine the first data packet
            while len(window_size) == window or seq-1 == last_loop and len(window_size) != 0:
                #Using error handling in case packets are discarded
                try:
                    #Sets a timout value to the client socket that raises a TimeoutError when 0,5 seconds has passed without any response from the server
                    client_socket.settimeout(timeout)
                    #Receives a 6-byte ACK packet from the server to acknowledge that a packet was received by the server
                    ack_packet, _ = client_socket.recvfrom(6)
                    #Unpacks the ACK packet into three variables, the packet's sequence number, the server's acknowledge number, and the flag value
                    server_seq, ack, flags = unpack_header(ack_packet)
                    #If statement that checks if the flag value equals an ack flag
                    if flags & ack_flag:
                        #If statement that checks if the packet's sequence number equals the acknowledgement number, also checks if they both equal the first sequence number in the sliding window
                        if server_seq == ack == window_size[0]:
                            #Reassigns the local time to a variable, needed each time local time is accessed
                            time_string = datetime.now().strftime("%H:%M:%S.%f")
                            print(time_string + " -- ACK for packet with seq number = "+str(ack)+" is received")
                            #Removes the acknowledged packet from the dictionary
                            packet_dict.pop(window_size[0])
                            #Removes the first packet from the sliding window, since it has been acknowledged by the server
                            window_size = window_size[1:]
                        else:
                            #If a discrepancy is found between the sequence numbers and acknowledge numbers, then a ValueError is raised
                            raise ValueError 
                
                except ConnectionResetError:
                    print("\n...\n\nLost contact with the server, terminating the connection")
                    client_socket.close()
                    sys.exit()

                #If a TimeoutError has been raised, the client assumes the server has discarded the sliding window's first packet, and resends it
                except (TimeoutError, ValueError):
                    #Reassigns the local time for use in the messages printed to the terminal
                    time_string = datetime.now().strftime("%H:%M:%S.%f")
                    print(time_string+" -- RTO occured")
                    #Initiates a GBN (Go-Back-N) sequence by resending all the packets in the sliding window
                    for key in window_size: #For loop that runs based on the length of the sliding window, since the client has to resend every packet within the window
                        #Reassigns the local time for use in the messages printed to the terminal
                        time_string = datetime.now().strftime("%H:%M:%S.%f")
                        print(time_string+" -- retransmitting lost packet with seq number "+str(key))
                        #Adds a variable that grabs the discarded packet from the packet dictionary by using the sequence number from the sliding window
                        discarded_packet = packet_dict[key]
                        #Resends the discarded packets to the server
                        client_socket.sendto(discarded_packet, server_address)

            #Increases the sequence number so each packet will get its own sequence number as id
            seq += 1
        
        #Sending a FIN packet after the for loop is finished to indicate that the file transfer is complete
        print("\nData transfer finished\n")
        print("Connection Teardown:\n")

        while True:
            client_socket.sendto(pack_header(0, 0, fin_flag), server_address) #Packs a header with only the fin_flag included ('0b0010', or 2 in decimal), seq and ack are unneeded
            print("FIN packet is sent")
            #Exception handling in case the client never receives a FIN-ACK packet from the server
            try:
                #Receives a 6-byte FIN-ACK packet from the server, acknowledging that the server received the FIN packet
                fin_ack_packet, _ = client_socket.recvfrom(6)
            #If a TimeoutError is triggered because no FIN-ACK packet was received, close the socket and terminate the program
            except TimeoutError:
                print("\n...\n\nThe server stopped responding, no FIN-ACK packet was received\n\n...\n\nResending FIN packet...")
                continue

            #Unpacks the header, only assigning the FIN-ACK flags to a variable as seq and ack are unneeded
            _, _, flags = unpack_header(fin_ack_packet)
            #If the flags variable is a bitwise combination of the fin flag and ack flag ('0b0110', or 6 in decimal), then it closes the client socket and terminates the connection
            if flags & fin_flag and flags & ack_flag:
                break

        print("FIN-ACK packet is received\n\nConnection Closes")
        client_socket.close()

#Argparse to enable argument parsing through the terminal
#-s enables the server, -c enables the client, -i determines the ip, -p determines the port, -f determines the filepath.
#-w determines the size of the sliding window, and -d determines which packet to discard during testing
parser = argparse.ArgumentParser(description='Run either the server or the client to receive or send a file to the set ip and port')
parser.add_argument('-s', '--server', help='Enables the server, on/off switch, accepts no arguments', action='store_true')
parser.add_argument('-c', '--client', help='Enables the client, on/off switch, accepts no arguments', action='store_true')
parser.add_argument('-i', '--ip', help='Only valid ipv4 addresses are allowed, default is 127.0.0.1', type=str, default='127.0.0.1')
parser.add_argument('-p', '--port', help='Port address, only the ports between [1024, 65535] are valid. Default is 8080', type=int, default=8080)
parser.add_argument('-f', '--file', help='File path, all file types are valid, max size is 60 MB, required for the client', type=str)
parser.add_argument('-w', '--window', help='Size of the sliding window used in the data transfer process, default is 3', type=int, default=3)
parser.add_argument('-d', '--discard', help='For use in testing, discards the selected packet during the data transfer process', type=int, default=float('inf'))
args = parser.parse_args()

#Checks if the ip address and port address are valid
check_ip(args.ip)
check_port(args.port)

#If statements that checks if the argument parsing by the user is correct, and prints a proper error message if not
if args.server and args.client:
    print("You cannot enable both the server and the client at the same time")
elif args.server:
    #Starts the server
    receive_file(args.ip, args.port, args.discard)
elif args.client:
    #Uses exception handling in case the file is not found
    try:
        #If statement that checks if a file path is provided in the terminal through an argparse argument, if not, terminates the program
        if not args.file:
            print("A file path has to be provided in the terminal through argparse arguments, write 'python3 application.py -h' in the terminal for more information")
            sys.exit()

        #If statement that checks if the file is larger than 60 MB, if so, terminates the program
        #Needed to prevent an error when sending packets, as the maximum packet number is 65535, which is easily reached when sending larger files with only 1000 byte packets
        elif os.path.getsize(args.file) > 60000000:
            print("The file has to be smaller than 60 MB, please choose a file with the proper file size")
            #Terminates the program
            sys.exit()

        #If statement to check if the sliding window size is valid
        elif args.window < 1:
            print("The sliding window size has to be larger than 0, please input a valid sliding window size")
            #Terminates the program
            sys.exit()

        #Starts the client
        send_file(args.ip, args.port, args.file, args.window)
    #If the file is not found, prints a proper error message and terminates the program
    except FileNotFoundError:
        print("The file path given cannot be found, please input a proper file path for the given file")
        sys.exit()
else:
    print("You have to enable either the server or the client to run this program, write 'python application.py -h' or 'python3 application.py -h' in the terminal for additional help")