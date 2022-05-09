#from tkinter.constants import COMMAND
from re import X
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as  tk
import tkinter.ttk as ttk
from tkinter import filedialog
from tkinter import messagebox as m_box
import numpy as np
import serial as sr
import serial.tools.list_ports
import time
import threading

#-----global variables-----
cond = False
cond_rec = False
paquete = False
cont_ppg = 0
cont_draw = 0
draw_RED = np.array([])
draw_IR = np.array([])

now = 0
lastupdate = 0
fps = 0
fps2 = 0

#-----plot data-----
def plot_data():
    global cond, draw_IR, draw_RED, paquete, cont_ppg, cont_draw, cond_rec, datos_IR, datos_RED, data_on
    
    decimacion = radioValue.get()
    cant_dec = int(150*20/decimacion)
    cant_dec_ant = int(cant_dec - 1)

    data_on = True
    while cond == True:
        if paquete == False:
            if int.from_bytes(s.read(), "big") == 35:               #detecta la trama de sincronismo
                if int.from_bytes(s.read(), "big") == 35:           #detecta la trama de sincronismo
                    if int.from_bytes(s.read(), "big") == 13:       #detecta la trama de sincronismo
                        if int.from_bytes(s.read(), "big") == 10:   #detecta la trama de sincronismo
                            paquete = True
        else:
            sample_RED = int.from_bytes(s.read(2), "big")   #los primeros dos bytes son led rojo
            sample_IR = int.from_bytes(s.read(2), "big")    #los siguientes dos bytes son led infrarojo

            if cond_rec == True:
                datos_RED = np.append(datos_RED,sample_RED) #si esta activado la grabacion guarda los datos
                datos_IR = np.append(datos_IR,sample_IR)

            cont_ppg += 1
            cont_draw += 1

            if cont_draw == decimacion:     #agrega datos nuevos en la grafica al cumplirse la condicion de decimacion
                cont_draw = 0
                if len(draw_RED) < cant_dec:
                    draw_RED = np.append(draw_RED,65536-sample_RED) #agrega datos al buffer de grafica
                    draw_IR = np.append(draw_IR,65536-sample_IR)
                else:
                    draw_RED[0:cant_dec_ant] = draw_RED[1:cant_dec] #elimina al inicio del buffer el dato mas viejo
                    draw_IR[0:cant_dec_ant] = draw_IR[1:cant_dec]
                    draw_RED[cant_dec_ant] = 65536-sample_RED       #agrega al final del buffer el dato nuevo
                    draw_IR[cant_dec_ant] = 65536-sample_IR
                
            if cont_ppg == 10:  #al completar el paquete de datos vuelve a buscar la trama de sincronismo
                cont_ppg = 0
                paquete = False
    data_on = False

def plot_draw():
    global draw_on, now, lastupdate, fps, fps2
    draw_on = True
    while cond == True: #mientras esté la condición dibuja
        ax[0].cla()
        ax[1].cla()
        ax[0].plot(np.arange(0,len(draw_RED)),draw_RED, color='orange')
        ax[1].plot(np.arange(0,len(draw_IR)),draw_IR, color='teal')
        canvas.draw()   #actualiza la grafica
        
        #Imprimo fps
        now = time.time()
        dt = (now-lastupdate)
        if dt <= 0:
            dt = 0.000000000001
        fps2 = 1.0 / dt
        lastupdate = now
        fps = fps * 0.9 + fps2 * 0.1
        tx = 'Mean Frame Rate:  {fps:.3f} FPS'.format(fps=fps )
        fps_text.set(tx)
    draw_on = False

def plot_close():
    global draw_RED, draw_IR
    while data_on == True or draw_on == True:
        continue
    s.close()
    del(draw_RED)
    del(draw_IR)
    draw_RED = np.array([])
    draw_IR = np.array([])
    m_box.showinfo('Serial Port','Puerto serie cerrado')

def serial_ports():
    return serial.tools.list_ports.comports()

#----- funcion de inicio de captura y ploteo -----
def change_state(desplegable): 
    global cond, s
    if desplegable.current() > -1:  
        puerto = desplegable.get()      #Toma el numero del puerto serie a abrir
        if cond == False:   #si el boton no estaba presionado antes ingresa
            try:
                s = sr.Serial(puerto.split()[0], 115200)    #intenta abrir el puerto
            except sr.SerialException:
                m_box.showerror('Error','Puerto serie ya abierto')  #en caso de fallar sale cartel de error
                return None
            s.reset_input_buffer()  #limpia buffer del puerto serie
            cond = True
            btn_text.set("Close")   #cambia el texto del boton
            threading.Thread(target=plot_data).start()  #inicia thread con la funcion de lectura
            threading.Thread(target=plot_draw).start()  #inicia thread con la funcion de ploteo
        else:
            cond = False
            btn_text.set("Open")    #cambia el texto del boton
            threading.Thread(target=plot_close).start() #inicia thread para cerrar la lectura y ploteo

#----- funcion de guardado -----
def change_rec():
    global cond_rec, datos_RED, datos_IR

    if cond_rec == False:   #si el boton no estaba presionado antes ingresa
        btn_rec_text.set("Grabando")    #cambia el texto del boton
        rec_btn.configure(bg="Red")     #cambia el color del boton
        datos_RED = np.array([])    #declara variables para almacenar los datos
        datos_IR = np.array([])
        cond_rec = True
    else:
        cond_rec = False    #al detener la grabacion salta la ventana para guardar el archivo
        file_data_name = filedialog.asksaveasfilename(defaultextension=".txt",title="Save File",filetypes=(("Text Files","*.txt"),("HTML","*.html")))
        
        if file_data_name:
            file_data_save = open(file_data_name.replace(".txt","RED.txt"), 'w')    #al nombre elegido del archivo le agrega una terminacion RED
            for row in datos_RED:
                file_data_save.write(str(row) + "\n")   #escribe el archivo con los datos RED
            file_data_save.close()  #cierra el archivo

            file_data_save = open(file_data_name.replace(".txt","IR.txt"), 'w')     #al nombre elegido del archivo le agrega una terminacion IR
            for row in datos_IR:
                file_data_save.write(str(row) + "\n")   #escribe el archivo con los datos IR
            file_data_save.close()  #cierra el archivo

        btn_rec_text.set("Grabar")  #cambia el texto y el color del boton
        rec_btn.configure(bg="Grey")


#-----------------------
#-----Main GUI code-----
#-----------------------
root = tk.Tk()                                              #Ventana Tkinter
root.title('GIBIO uFisio - Fotopletismografo (RED - IR)')   #Titulo
root.config(background='white')                             #Fondo
root.geometry("1000x700")                                   #Dimensiones
#canvass = tk.Canvas(root, width=600, height=300)
#canvass.grid(columnspan=60, rowspan=30)

#-----Create plot object on GUI-----
fig = Figure()                      #Figura de ploteo
#ax = fig.add_subplot(111)
ax = fig.subplots(2)                #Dos subplots
ax[0].set_xlim(0,150)               #limite eje x
ax[1].set_xlim(0,150)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().place(x=10,y=10,width=1000,height=700)
canvas.draw()

#-----create radio button-----
labelRadio = tk.Label(root, text = "Graficar cada:")
labelRadio.place(x=0,y=0)
radioValue = tk.IntVar()
rdio1 = tk.Radiobutton(root, text='20 samples', variable=radioValue, value=20)
rdio2 = tk.Radiobutton(root, text='10 samples', variable=radioValue, value=10)
rdio3 = tk.Radiobutton(root, text='5 samples', variable=radioValue, value=5)
#rdio4 = tk.Radiobutton(root, text='2 samples', variable=radioValue, value=2)
radioValue.set(20)

rdio1.place(x=0, y=20)
rdio2.place(x=0, y=40)
rdio3.place(x=0, y=60)
#rdio4.place(x=0, y=80)

#-----create box serial port-----
labelTop = tk.Label(root, text = "Elegir puerto serie:")
labelTop.place(x=250)

fps_text = tk.StringVar()
labelFPS = tk.Label(root, textvariable = fps_text)
fps_text.set("FPS:")
labelFPS.place(x=50, y=650)

root.update()
desple = ttk.Combobox(root, width="40", values=serial_ports(),state="readonly")
desple.place(x=360)
#desple.pack()

#-----create button-----
root.update()
btn_text = tk.StringVar()
open_btn = tk.Button(root, textvariable=btn_text, command=lambda:change_state(desple), font="Raleway", bg="#20bebe", fg="white", height=1, width=5)
btn_text.set("Open")
open_btn.place(x=650)

root.update()
btn_rec_text = tk.StringVar()
rec_btn = tk.Button(root, textvariable=btn_rec_text, command=lambda:change_rec(), font="Raleway", bg="grey", fg="white", height=1, width=7)
btn_rec_text.set("Grabar")
rec_btn.place(x=750)

root.mainloop()