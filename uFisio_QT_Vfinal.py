# -*- coding: utf-8 -*-
"""
Created on Tue May  3 15:26:18 2022

@author: Alejo
"""

# importing Qt widgets
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QApplication, QComboBox, QGridLayout, QPushButton, QLineEdit
 
# importing system
import sys
 
# importing numpy as np
import numpy as np

# importing pyqtgraph as pg
import pyqtgraph as pg

#import pyqtgraph.ptime as ptime

import serial as sr
import serial.tools.list_ports

import time

#-----global variables-----
cond = False
cond_rec = False
paquete = False
cont_ppg = 0
cont_draw = 0

draw_RED = np.array([])
draw_IR = np.array([])

datos_RED = np.array([])
datos_IR = np.array([])
datos_tiempo = np.array([])


data_modif = False

FPS_USUARIO = 0

tiempo_medido = 0
vector_tiempo = np.array([])

tiempo_inicio = 0

def serial_ports():
    return serial.tools.list_ports.comports()

class Thread_Lectura(QThread):
    #datosLeidos = pyqtSignal(list)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def run(self) -> None:
        global acceso_datos, cond, draw_IR, draw_RED, paquete, cont_ppg, cont_draw, cond_rec, datos_IR, datos_RED,datos_tiempo, window, data_modif, tiempo_medido, vector_tiempo
        
        decimacion = 20

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
                                
                if (65536-sample_RED)>50000:
                    sample_RED = 15536
                    
                if (65536-sample_IR)>50000:
                    sample_IR = 15536
                

                if cond_rec == True:
                    datos_RED = np.append(datos_RED,65536-sample_RED) #si esta activado la grabacion guarda los datos
                    datos_IR = np.append(datos_IR,65536-sample_IR)
                    datos_tiempo = np.append(datos_tiempo,tiempo_medido)
        
                cont_ppg += 1
                cont_draw += 1
        
                if cont_draw == decimacion:     #agrega datos nuevos en la grafica al cumplirse la condicion de decimacion
                    cont_draw = 0
                    data_modif = True
                    
                    tiempo_medido = time.time()-tiempo_inicio
                    
                    if tiempo_medido < 3:
                        
                        draw_RED = np.append(draw_RED,65536-sample_RED) #agrega datos al buffer de grafica
                        draw_IR = np.append(draw_IR,65536-sample_IR)
                        vector_tiempo = np.append(vector_tiempo, tiempo_medido)
                        
                    else:
                        draw_RED[0:(len(vector_tiempo)-1)] = draw_RED[1:len(vector_tiempo)] #elimina al inicio del buffer el dato mas viejo
                        draw_IR[0:(len(vector_tiempo)-1)] = draw_IR[1:len(vector_tiempo)]
                        vector_tiempo[0:(len(vector_tiempo)-1)] = vector_tiempo[1:len(vector_tiempo)]
                        
                        draw_RED[len(vector_tiempo)-1] = 65536-sample_RED       #agrega al final del buffer el dato nuevo
                        draw_IR[len(vector_tiempo)-1] = 65536-sample_IR
                        vector_tiempo[len(vector_tiempo)-1] = tiempo_medido
                        
                    data_modif = False
                              
                if cont_ppg == 10:  #al completar el paquete de datos vuelve a buscar la trama de sincronismo
                    cont_ppg = 0
                    paquete = False
    

def conexion_serie(lista_puertos): 
    global cond, s, Thread_Timeado, data_on, window, T1, draw_RED, draw_IR, tiempo_inicio, vector_tiempo
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
            T1 = Thread_Lectura()#inicia thread con la funcion de lectura
            T1.start()
            window.timer_FPS.start(1000/FPS_USUARIO) #FPS definido por usuario
            
            tiempo_inicio = time.time()
            #threading.Thread(target=plot_draw).start()  #inicia thread con la funcion de ploteo
            #Thread_Timeado = RepeatTimer(3, plot_draw) #inicia thread con la funcion de ploteo
            #Thread_Timeado.start()
        else:
            cond = False
            window.boton_start.setText("Abrir Puerto") #cambia el texto del boton
            
            T1.exit()
            T1.wait()

            del(T1)

            s.close()

            window.timer_FPS.stop()
            
            vector_tiempo = np.resize(vector_tiempo, 0)
            draw_RED = np.resize(draw_RED, 0)
            draw_IR = np.resize(draw_IR, 0)
            

class ComboBox(QComboBox):
    
    def showPopup(self):
        
        self.clear()
        for i in range(len(serial_ports())):
            self.addItem(serial_ports()[i].name)
        
        super(ComboBox, self).showPopup()

class Window(QMainWindow):
 
    timer_FPS = 0
    lista_puertos = 0
    boton_start = 0
    boton_grabar = 0
    plot_RED = 0
    plot_IR = 0
    canvas_RED = 0
    canvas_IR = 0
    label_fps = 0
    buttonGroup = 0
    FPS_USUARIO = 0
    
    def __init__(self):
        super().__init__()
 
        # setting title
        self.setWindowTitle("GIBIO uFisio - Fotopletismografo (RED - IR)")
 
        # setting geometry
        self.setGeometry(100, 100, 1000, 700)
        
        self.setStyleSheet("background-color: rgb(20,20,20);")
        
        # icon
        #icon = QIcon("skin.png")
 
        # setting icon to the window
        #self.setWindowIcon(icon)        
 
        # calling method
        self.UiComponents()
 
        # showing all the widgets
        self.show()
        
        self.timer_FPS = QTimer()
        self.timer_FPS.timeout.connect(self.plot)

 
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

        self.label_fps = QLabel("FPS:")
        self.label_fps.setStyleSheet("QLabel { color : white; }")
        
        layout.addWidget(self.label_fps, 0, 0, QtCore.Qt.AlignRight)

        self.FPS_LineEdit = QLineEdit()
        self.FPS_LineEdit.setStyleSheet("QLineEdit { color : white; }")
        self.FPS_LineEdit.textChanged[str].connect(self.onChanged)
        
        self.FPS_LineEdit.setMaximumWidth(130)
        
        layout.addWidget(self.FPS_LineEdit, 0, 1, QtCore.Qt.AlignLeft)
        
        self.FPS_LineEdit.setText("24")
 
        # creating a label
        label = QLabel("Puerto Serie:")
        label.setStyleSheet("QLabel { color : white; }")
        
        # adding label in the layout
        layout.addWidget(label, 0, 2, QtCore.Qt.AlignRight)


        self.lista_puertos = ComboBox()
        
        self.lista_puertos.setMinimumWidth(130)
        
        self.lista_puertos.setStyleSheet("background-color: rgb(100,100,100);")
        
        self.lista_puertos.addItem("Seleccionar Puerto")
        
        layout.addWidget(self.lista_puertos, 0, 3, QtCore.Qt.AlignLeft)
        
        self.boton_start = QPushButton("Abrir Puerto")
        self.boton_start.clicked.connect(lambda:conexion_serie(self.lista_puertos))
        
        self.boton_start.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_start, 0, 4)
        
        self.boton_grabar = QPushButton("Grabar")
        self.boton_grabar.clicked.connect(self.Grabar)
        
        self.boton_grabar.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_grabar, 0, 5)
        
        
        pg.setConfigOption('background', pg.mkColor(20,20,20))
        pg.setConfigOption('foreground', 'w')
    
        # creating a graph item
        self.canvas_RED = pg.PlotWidget(title="RED")
        self.canvas_IR = pg.PlotWidget(title="IR")
        #self.canvas_RED.setXRange(0,150, padding = 0)
        
        
        #canvas_RED.setXRange(0, 150, padding=0) #limite eje x
        #canvas_IR.setXRange(0, 150, padding=0)
        
        # plot window goes on right side, spanning 3 rows
        layout.addWidget(self.canvas_RED, 1, 0, 1, 6)
        layout.addWidget(self.canvas_IR, 2, 0, 1, 6)
        
        self.plot_RED = self.canvas_RED.plot(pen=pg.mkPen(color = (255,0,0), width = 3))
        self.plot_IR = self.canvas_IR.plot(pen=pg.mkPen(color = (255,255,0), width = 3))

        # setting this widget as central widget of the main window
        self.setCentralWidget(widget)
 
        # getting padding of graph item
        #value = plot_RED.pixelPadding()
 
        # setting text to the label
        #label.setText("Padding : " + str(value))
    
    @QtCore.pyqtSlot()
    def plot(self):
        while data_modif == True:
            continue
            
        window.plot_RED.setData(vector_tiempo, draw_RED)
        window.plot_IR.setData(vector_tiempo, draw_IR)
    

    def onChanged(self, text):
        global FPS_USUARIO
        if text.isnumeric():
            FPS_USUARIO = int(str(text))
            if cond == True:
                window.timer_FPS.start(1000/FPS_USUARIO) #Para que se actualicen los FPS mientras imprime
        else:
            print("FPS INVALIDO")
    @QtCore.pyqtSlot()        
    def Grabar (self):
        global cond_rec,datos_tiempo,datos_RED,datos_IR
        if cond_rec == False  :      
            self.boton_grabar.setText("Stop")

            cond_rec = True
        else:
            cond_rec = False
            mediciones = open("Mediciones_Nombre.txt",'w')

            mediciones.truncate(0)

            self.boton_grabar.setText("Grabar")
            
            mediciones.write('Tiempo\t\t\tRojo\t\t\tInfrarrojo\n')
            
            for i in range(len(datos_tiempo)):
                mediciones.write(str(datos_tiempo[i])+'\t'+str(datos_RED[i]) +'\t'+ str(datos_IR[i]) +'\n')
            mediciones.close()
            
            datos_tiempo = np.resize(datos_tiempo, 0)
            datos_RED = np.resize(datos_RED, 0)
            datos_IR = np.resize(datos_IR, 0)
            

# create pyqt5 app
App = QApplication(sys.argv)
 
# create the instance of our Window
window = Window()

# start the app
sys.exit(App.exec())