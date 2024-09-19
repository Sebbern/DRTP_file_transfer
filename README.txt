EDIT: Keep in mind that the code is excessively over-commented due to the task's requirements. I find the code harder to read because of it, and will remove quite a few of them at a later date.

This program copies a file from a designated file path to the program's local folder.

To run the program application.py, you would need to unzip the src folder wherever you like.

From there on you can either open two terminals and start either the server or client by using the command-line arguments:
"python3 application.py -s -i <ip> -p <port>" for the server
"python3 application.py -c -i <ip> -p <port> -f <file_path> -w <window_size>" for the client, where <file_path> is the file path to the file that you want to transfer to the server. The window size isn't optional, but it is set to 3 as default, so it doesn't have to be an argument provided by the user.
ip and port defaults to 127.0.0.1 and 8080 if they aren't provided, but if you provide an ip or port for the server, you HAVE to provide the same ip or port for the client arguments.
The server also has an optional discard function "-d <packet_number>" that can be used in testing. Write "python3 application.py -h" for additional information

Note: Depending on your settings, you might need to write "python" instead of "python3" in the beginning of each command-line argument as well, so take note of that if the program isn't runable.

If you are using simple-topo.py through mininet, then first run simple-topo.py using the command:
"sudo python3 simple-topo.py".
After running simple-topo.py, mininet will be opened, then use the command:
"xterm h1 h2" to open two terminals

It is vital that h2 is the server and h1 is the client for application.py to work

For the results in discussion 1, use the command-line arguments:
"python3 application.py -s -i 10.0.1.2 -p 8080" for h2 (the server)
"python3 application.py -c -i 10.0.1.2 -p 8080 -f <file_path> -w 3" for h1 (the client), <file_path> is the file path to the file that you want to send to the server, use -w 3, -w 5, or -w 10 to replicate the various results.

For the results in discussion 2, change the RTT on line 43 in simple-topo.py from 100ms to 50ms or 200ms depending on what results you want. Then use the same command-line arguments as written above to produce the results.

For the results in discussion 3, revert the RTT on line 43 in simple-topo.py back to 100ms, then use the command-line arguments:
"python3 application.py -s -i 10.0.1.2 -p 8080 -d 10" for h2 (the server)
"python3 application.py -c -i 10.0.1.2 -p 8080 -f <file_path> -w 5" for h1 (the client), where <file_path> is the file path to the file that you want to send to the server.

For the results in discussion 4, comment line 43 in simple-topo.py and uncomment line 44. At the same time change the RTT on line 44 to 100ms and the loss on line 44 to either 2% or 5%. Then use these command-line arguments to produce the results:
"python3 application.py -s -i 10.0.1.2 -p 8080" for h2 (the server)
"python3 application.py -c -i 10.0.1.2 -p 8080 -f <file_path> -w 3" (the client), where <file_path> is the file path to the file that you want to send to the server.

NOTE: Keep in mind that you have to quit mininet and restart simple-topo.py each time you edit the file to get the desired results.
