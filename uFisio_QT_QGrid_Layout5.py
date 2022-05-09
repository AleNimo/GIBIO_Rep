# -*- coding: utf-8 -*-
"""
Created on Tue May  3 15:26:18 2022

@author: Alejo
"""

# importing Qt widgets
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QApplication, QComboBox, QGridLayout, QPushButton, QButtonGroup, QRadioButton
 
# importing system
import sys
 
# importing numpy as np
import numpy as np

# importing pyqtgraph as pg
import pyqtgraph as pg

#import pyqtgraph.ptime as ptime

import serial as sr
import serial.tools.list_ports

import threading
from threading import Timer

import time

#-----global variables-----
cond = False
cond_rec = False
paquete = False
cont_ppg = 0
cont_draw = 0

draw_RED = np.array([])
draw_IR = np.array([])

Thread_Timeado = 0
acceso_datos = False

now = 0
lastupdate = 0
fps = 0
fps2 = 0

data_on = False


def serial_ports():
    return serial.tools.list_ports.comports()

def plot_data():
    global acceso_datos, cond, draw_IR, draw_RED, paquete, cont_ppg, cont_draw, cond_rec, datos_IR, datos_RED, data_on, window, now, lastupdate, fps, fps2
    
    
    
    
    
    while 1:
        
        decimacion = 5
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
        
                # if cond_rec == True:
                #     datos_RED = np.append(datos_RED,sample_RED) #si esta activado la grabacion guarda los datos
                #     datos_IR = np.append(datos_IR,sample_IR)
        
                cont_ppg += 1
                cont_draw += 1
        
                if cont_draw == decimacion:     #agrega datos nuevos en la grafica al cumplirse la condicion de decimacion
                    cont_draw = 0
                    acceso_datos = True
                    if len(draw_RED) < cant_dec:
                        draw_RED = np.append(draw_RED,65536-sample_RED) #agrega datos al buffer de grafica
                        draw_IR = np.append(draw_IR,65536-sample_IR)
                    else:
                        draw_RED[0:cant_dec_ant] = draw_RED[1:cant_dec] #elimina al inicio del buffer el dato mas viejo
                        draw_IR[0:cant_dec_ant] = draw_IR[1:cant_dec]
                        draw_RED[cant_dec_ant] = 65536-sample_RED       #agrega al final del buffer el dato nuevo
                        draw_IR[cant_dec_ant] = 65536-sample_IR
                    acceso_datos = False
                    window.plot_RED.setData(np.arange(0,len(draw_RED)), draw_RED)
                    window.plot_IR.setData(np.arange(0,len(draw_IR)), draw_IR)
                    
                    #Imprimo fps
                    now = time.time()
                    dt = (now-lastupdate)
                    if dt <= 0:
                        dt = 0.000000000001
                    fps2 = 1.0 / dt
                    lastupdate = now
                    fps = fps * 0.9 + fps2 * 0.1
                    tx = 'Mean Frame Rate:  {fps:.3f} FPS'.format(fps=fps )
                    window.label_fps.setText(tx)
                    
                if cont_ppg == 10:  #al completar el paquete de datos vuelve a buscar la trama de sincronismo
                    cont_ppg = 0
                    paquete = False
        data_on = False
    

# def plot_draw():
#     global draw_on, window
#     draw_on = True
#     while cond == True: #mientras esté la condición dibuja  
#         if acceso_datos == False:
#             window.canvas_RED.plot(np.arange(0,len(draw_RED)), draw_RED)
#         #window.plot_IR.setData(draw_IR)
#     draw_on = False


# def plot_close():
#     global draw_RED, draw_IR, draw_on
       
#     while data_on == True:
#         continue
#     s.close()
#     del(draw_RED)
#     del(draw_IR)
#     draw_RED = np.array([])
#     draw_IR = np.array([])
#     #m_box.showinfo('Serial Port','Puerto serie cerrado')

def conexion_serie(lista_puertos): 
    global cond, s, Thread_Timeado, data_on, window
    puerto = lista_puertos.currentText()
    if puerto != "":
        
        if cond == False:   #si el boton no estaba presionado antes ingresa
            try:
                s = sr.Serial(puerto.split()[0], 115200)    #intenta abrir el puerto
            except sr.SerialException:
                #m_box.showerror('Error','Puerto serie ya abierto')  #en caso de fallar sale cartel de error
                return None
            s.reset_input_buffer()  #limpia buffer del puerto serie
            cond = True
            window.boton_start.setText("Cerrar Puerto") #cambia el texto del boton
            
            #threading.Thread(target=plot_draw).start()  #inicia thread con la funcion de ploteo
            #Thread_Timeado = RepeatTimer(3, plot_draw) #inicia thread con la funcion de ploteo
            #Thread_Timeado.start()
        else:
            cond = False
            window.boton_start.setText("Abrir Puerto") #cambia el texto del boton
            
            while data_on == True:
                continue
            s.close()
            
            #threading.Thread(target=plot_close).start() #inicia thread para cerrar la lectura y ploteo
            
            
            

def inicio():
    
    T1 = threading.Thread(target = plot_data)  #inicia thread con la funcion de lectura
    T1.start()
            
class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

class Window(QMainWindow):
 
    lista_puertos = 0
    boton_start = 0
    plot_RED = 0
    plot_IR = 0
    canvas_RED = 0
    canvas_IR = 0
    label_fps = 0
    buttonGroup = 0
    
    def __init__(self):
        super().__init__()
 
        # setting title
        self.setWindowTitle("GIBIO uFisio - Fotopletismografo (RED - IR)")
 
        # setting geometry
        self.setGeometry(100, 100, 1000, 700)
        
        self.setStyleSheet("background-color: QColor(20,20,20);")
        
        # icon
        #icon = QIcon("skin.png")
 
        # setting icon to the window
        #self.setWindowIcon(icon)        
 
        # calling method
        self.UiComponents()
 
        # showing all the widgets
        self.show()
 
    # method for components
    def UiComponents(self):
 
        # creating a widget object
        widget = QWidget()
 
        # setting minimum width
        #label.setMinimumWidth(130)
 
        # making label do word wrap
        #label.setWordWrap(True)
 
        # setting configuration options
        pg.setConfigOptions(antialias=True)

        # Creating a grid layout
        layout = QGridLayout()
        
        # setting this layout to the widget
        widget.setLayout(layout)
 
        # creating a label
        label = QLabel("Puerto Serie:")
        label.setStyleSheet("QLabel { color : white; }")
        
        # adding label in the layout
        layout.addWidget(label, 0, 0, QtCore.Qt.AlignRight)


        self.lista_puertos = QComboBox()
        
        self.lista_puertos.setMinimumWidth(130)
        
        self.lista_puertos.setStyleSheet("background-color: rgb(100,100,100);")
        
        for i in range(len(serial_ports())):
            self.lista_puertos.addItem(serial_ports()[i].name)
        
        layout.addWidget(self.lista_puertos, 0, 1, QtCore.Qt.AlignLeft)
        
        self.boton_start = QPushButton("Abrir Puerto")
        self.boton_start.clicked.connect(lambda:conexion_serie(self.lista_puertos))
        
        self.boton_start.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_start, 0, 2)
        
        pg.setConfigOption('background', pg.mkColor(20,20,20))
        pg.setConfigOption('foreground', 'w')
    
        # creating a graph item
        self.canvas_RED = pg.PlotWidget(title="RED")
        self.canvas_IR = pg.PlotWidget(title="IR")
        
        
        #canvas_RED.setXRange(0, 150, padding=0) #limite eje x
        #canvas_IR.setXRange(0, 150, padding=0)
        
        # plot window goes on right side, spanning 3 rows
        layout.addWidget(self.canvas_RED, 4, 0, 1, 3)
        layout.addWidget(self.canvas_IR, 5, 0, 1, 3)
        
        self.plot_RED = self.canvas_RED.plot(pen=pg.mkPen(color = (255,0,0), width = 3))
        self.plot_IR = self.canvas_IR.plot(pen=pg.mkPen(color = (255,255,0), width = 3))
        
        label_samples = QLabel("Graficar cada:")
        label_samples.setStyleSheet("QLabel { color : white; }")
        
        radButton_20 = QRadioButton("20 Samples")
        radButton_20.setStyleSheet("QRadioButton{ color : white; }")
        
        radButton_10 = QRadioButton("10 Samples")
        radButton_10.setStyleSheet("QRadioButton{ color : white; }")
        
        radButton_5 = QRadioButton("5 Samples")
        radButton_5.setStyleSheet("QRadioButton{ color : white; }")
        
        radButton_20.setChecked(True)
        
        self.buttonGroup = QButtonGroup()
        
        self.buttonGroup.addButton(radButton_20, 20)
        self.buttonGroup.addButton(radButton_10, 10)
        self.buttonGroup.addButton(radButton_5, 5)
        
        layout.addWidget(label_samples, 0, 0)
        layout.addWidget(radButton_5, 1, 0)
        layout.addWidget(radButton_10, 2, 0)
        layout.addWidget(radButton_20, 3, 0)
        
        ##########
        self.label_fps = QLabel("FPS:")
        self.label_fps.setStyleSheet("QLabel { color : white; }")
        layout.addWidget(self.label_fps, 6, 0)
        ##########
        
 
        # setting this widget as central widget of the main window
        self.setCentralWidget(widget)
 
        # getting padding of graph item
        #value = plot_RED.pixelPadding()
 
        # setting text to the label
        #label.setText("Padding : " + str(value))
        
# create pyqt5 app
App = QApplication(sys.argv)
 
# create the instance of our Window
window = Window()

QtCore.QTimer().singleShot(1000,    lambda :inicio())

sys.exit()



# start the app
#App.exec())