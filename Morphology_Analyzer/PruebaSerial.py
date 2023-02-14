# import serial as sr
# import serial.tools.list_ports

# try:
#     s = sr.Serial(puerto.split()[0], 115200)    #intenta abrir el puerto
# except sr.SerialException:
#     print("Error al abrir puerto")
#     #m_box.showerror('Error','Puerto serie ya abierto')  #en caso de fallar sale cartel de error

# s.

import win32com.client
wmi = win32com.client.GetObject("winmgmts:")
for serial in wmi.InstancesOf("Win32_SerialPort"):
       print (serial.Name, serial.Description, serial. )

