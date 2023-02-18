# -*- coding: utf-8 -*-
"""
Created on Tue May  3 15:26:18 2022

@author: Alejo
"""

# importing Qt widgets
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QApplication, QComboBox, QGridLayout, QPushButton, QLineEdit, QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QCheckBox
from PyQt5.QtGui import QFont

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

#Librería para medir la velocidad de propagación
from Morphology_Analyzer import Morphology_Analyzer as MA

# import os to create directory
import os

#-----global variables-----
fs = 1000

cond = False
cond_rec = False
paquete = False
cont_ppg = 0
cont_draw = 0

raw_RED = np.array([])
raw_IR = np.array([])
raw_ECG = np.array([])

draw_RED = np.array([])
draw_IR = np.array([])
draw_ECG = np.array([])
draw_tiempo = np.array([])

datos_RED = np.array([])
datos_IR = np.array([])
datos_ECG = np.array([])

data_modif = False

FPS_USUARIO = 24

decimacion = 10

tiempo_medido = 0

tiempo_inicio = 0

paciente = np.array(["NOMBRE_APELLIDO", '-', '-', '-', '-'])

pacienteIngresado = False

pausarThread = False

threadPausado = False

T1 = 0

VOP = 0
VOP_std_exp = 0

dark_mode  = False  #Modo oscuro / Modo claro

def serial_ports():
    return serial.tools.list_ports.comports()

class Thread_Lectura(QThread):
    #datosLeidos = pyqtSignal(list)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def run(self) -> None:
        global acceso_datos, cond, raw_IR, raw_RED, raw_ECG, draw_ECG, draw_RED, draw_IR, draw_tiempo, paquete, cont_ppg, cont_draw, cond_rec, datos_IR, datos_RED, datos_ECG, window, data_modif, tiempo_medido, decimacion, pausarThread, threadPausado

        while cond == True:
        
            # while pausarThread == True:
                # threadPausado = True
            
            # threadPausado = False
            
            if paquete == False:
                if int.from_bytes(s.read(), "big") == 35:               #detecta la trama de sincronismo
                    if int.from_bytes(s.read(), "big") == 35:           #detecta la trama de sincronismo
                        if int.from_bytes(s.read(), "big") == 13:       #detecta la trama de sincronismo
                            if int.from_bytes(s.read(), "big") == 10:   #detecta la trama de sincronismo
                                paquete = True
            else:
                sample_RED = int.from_bytes(s.read(2), "big")   #los primeros dos bytes son del led rojo
                sample_IR = int.from_bytes(s.read(2), "big")    #los siguientes dos bytes son del led infrarojo

                if window.ECG_activo:
                    sample_ECG = int.from_bytes(s.read(2), "big")    #los siguientes dos bytes son del ECG
                else:
                    sample_ECG = 0
                
                if window.inversion_canales:    #Para fotopletismografo se deben invertir las curvas
                    sample_RED = 65535 - sample_RED   #los primeros dos bytes son led rojo
                    sample_IR = 65535 - sample_IR    #los siguientes dos bytes son led infrarojo

                #Filtramos el ruido cuando no se mide nada, para no sobrecargar el plotter
                # if sample_RED > 15536:
                #     sample_RED = 15536
                
                # if sample_IR > 15536:
                #     sample_IR = 15536

                if cond_rec == True:
                    datos_RED = np.append(datos_RED,sample_RED) #si esta activado la grabacion guarda los datos
                    datos_IR = np.append(datos_IR,sample_IR)
                    datos_ECG = np.append(datos_ECG,sample_ECG)
        
                cont_ppg += 1
                cont_draw += 1
                
                if tiempo_medido < 20:  #Tiempo mínimo necesario para calcular la VOP
                    
                    raw_RED = np.append(raw_RED,sample_RED) #agrega datos al buffer de grafica
                    raw_IR = np.append(raw_IR,sample_IR)
                    raw_ECG = np.append(raw_ECG,sample_ECG)
                    
                    if cont_draw == decimacion:  #agrega datos nuevos en la grafica al cumplirse la condicion de decimacion
                        cont_draw = 0

                        tiempo_medido = time.time()-tiempo_inicio
                        
                        data_modif = True
                        draw_RED = np.append(draw_RED,sample_RED)
                        draw_IR = np.append(draw_IR,sample_IR)
                        draw_ECG = np.append(draw_ECG,sample_ECG)
                        draw_tiempo = np.append(draw_tiempo, tiempo_medido)
                        data_modif = False
                    
                else:
                    
                    raw_RED = shift_array(raw_RED, -1)    #Se desplazan los vectores 
                    raw_IR = shift_array(raw_IR, -1)
                    raw_ECG = shift_array(raw_ECG, -1)
                    
                    raw_RED[len(raw_RED)-1] = sample_RED       #agrega al final del buffer el dato nuevo
                    raw_IR[len(raw_IR)-1] = sample_IR
                    raw_ECG[len(raw_ECG)-1] = sample_ECG

                    if cont_draw == decimacion:
                        cont_draw = 0
                        
                        tiempo_medido = time.time()-tiempo_inicio
                        
                        data_modif = True
                        
                        draw_RED = shift_array(draw_RED, -1) #Se desplazan los vectores 
                        draw_IR = shift_array(draw_IR, -1)
                        draw_ECG = shift_array(draw_ECG, -1)
                        draw_tiempo = shift_array(draw_tiempo, -1)
                        
                        draw_RED[len(draw_RED)-1] = sample_RED   #agrega al final del buffer el dato nuevo
                        draw_IR[len(draw_IR)-1] = sample_IR
                        draw_ECG[len(draw_ECG)-1] = sample_ECG
                        draw_tiempo[len(draw_tiempo)-1] = tiempo_medido
                        
                        data_modif = False
                
                if cont_ppg == 10:  #al completar el paquete de datos vuelve a buscar la trama de sincronismo
                    cont_ppg = 0
                    paquete = False

def conexion_serie(puertoActual): 
    global cond, s, Thread_Timeado, data_on, window, T1, draw_RED, draw_IR, draw_ECG, raw_RED, raw_IR, raw_ECG, tiempo_inicio, draw_tiempo, tiempo_medido

    if puertoActual != "":
        
        if cond == False:   #si el boton no estaba presionado antes ingresa
            
            try:
                s = sr.Serial(puertoActual.split()[0], 115200)    #intenta abrir el puerto
            except sr.SerialException:
                print("Error al abrir puerto")
                #m_box.showerror('Error','Puerto serie ya abierto')  #en caso de fallar sale cartel de error
                return
            # if s.isOpen():
            #     s.close()
            # s.open()
            
            s.reset_input_buffer()  #limpia buffer del puerto serie
            cond = True

            T1 = Thread_Lectura()#inicia thread con la funcion de lectura
            T1.start()

            tiempo_inicio = time.time()
            
            window.timer_FPS.start(int(1000/FPS_USUARIO)) #FPS definido por usuario
            window.boton_freeze.setText('Congelar')            
            
            window.boton_freeze.setEnabled(True)
            window.boton_grabar.setEnabled(True)
        else:
            if(cond_rec==False):
                cond = False
                
                del(T1)
                s.close()
                
                window.timer_FPS.stop()
                window.timer_VOP.stop()
                
                tiempo_medido = 0
                draw_tiempo = np.resize(draw_tiempo, 0)
                draw_RED = np.resize(draw_RED, 0)
                draw_IR = np.resize(draw_IR, 0)
                draw_ECG = np.resize(draw_ECG, 0)
                
                raw_RED = np.resize(raw_RED, 0)
                raw_IR = np.resize(raw_IR, 0)
                raw_ECG = np.resize(raw_ECG, 0)
                
                window.boton_freeze.setEnabled(False)
                window.boton_grabar.setEnabled(False)
            else:
            
                
                msgBox = QMessageBox()
                msgBox.setStyleSheet("QLabel { color : white; } QMessageBox {background-color: rgb(100,100,100);}")
                msgBox.setWindowTitle("Error Al Cerrar Puerto")
                msgBox.setText("Pause la grabacion antes de cerrar el puerto.")
                msgBox.exec()        

class ComboBox(QComboBox):
    def __init__(self):
        super(ComboBox, self).__init__()
        for i in range(len(serial_ports())):
            self.addItem(serial_ports()[i].name)
        
        self.addItem("Seleccionar Puerto")
        
    def showPopup(self):
        
        self.clear()
        for i in range(len(serial_ports())):
            self.addItem(serial_ports()[i].name)
        
        super(ComboBox, self).showPopup()

class Patient_InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.name = QLineEdit(self)
        self.age = QLineEdit(self)
        self.dist_cf = QLineEdit(self)
        self.PAS = QLineEdit(self)  #systolic brachial pressure
        self.PAD = QLineEdit(self)  #diastolic brachial pressure
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)

        layout = QFormLayout(self)
        
        layout.addRow("Nombre:", self.name)
        layout.addRow("Edad:", self.age)
        layout.addRow("Distancia Carótida-Femoral (cm):", self.dist_cf)
        layout.addRow("Presión Sistólica Braquial:", self.PAS)
        layout.addRow("Presión Diastólica Braquial:", self.PAD)
        
        layout.addWidget(buttonBox)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        self.setStyleSheet("QLabel { background-color: rgb(80,80,80); color : white; } QLineEdit { background-color: rgb(50,50,50); color : white;} QDialog{ background-color: rgb(80,80,80)} ")
        buttonBox.button(QDialogButtonBox.Ok).setStyleSheet("background-color: rgb(80,80,80); color: white")
        buttonBox.button(QDialogButtonBox.Cancel).setStyleSheet("background-color: rgb(80,80,80); color: white")

    def getInputs(self):
        return (self.name.text(), self.age.text(), self.dist_cf.text(), self.PAS.text(), self.PAD.text())

class Config_InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)

        label_puerto_serie = QLabel("Puerto Serie:")

        # Lista de puertos serie
        self.lista_puertos = ComboBox()
        self.lista_puertos.setMinimumWidth(130)
        if dark_mode:
            self.lista_puertos.setStyleSheet("background-color: rgb(100,100,100);")
        else:
            self.lista_puertos.setStyleSheet("background-color: rgb(200,200,200);")

        # Checkbox para inversion de canales
        self.checkbox_invertir = QCheckBox("Invertir")
        self.checkbox_invertir.setTristate(False)
        #self.checkbox_invertir.setStyleSheet("QCheckBox { color : white; }")

        # Checkbox para graficar ECG o no
        self.checkbox_canales = QCheckBox("ECG Activo")
        self.checkbox_canales.setTristate(False)
        #self.checkbox_canales.setStyleSheet("QCheckBox { color : white; }")

        # Checkbox para calcular VOP o no
        self.checkbox_VOP = QCheckBox("VOP Continua")
        self.checkbox_VOP.setTristate(False)

        # Botones de cancelar y ok
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        buttonBox.button(QDialogButtonBox.Ok).setStyleSheet("background-color: rgb(80,80,80); color: white")
        buttonBox.button(QDialogButtonBox.Cancel).setStyleSheet("background-color: rgb(80,80,80); color: white")

        ############################################################################

        layout.addWidget(label_puerto_serie,     0,0)
        layout.addWidget(self.lista_puertos,     0,1)
        layout.addWidget(self.checkbox_canales,  1,0)
        layout.addWidget(self.checkbox_invertir, 2,0)
        layout.addWidget(self.checkbox_VOP,      3,0)
        layout.addWidget(buttonBox,              4,0) #QtCore.Qt.AlignLeft
        
        self.setStyleSheet("QLabel { background-color: rgb(80,80,80); color : white; } QLineEdit { background-color: rgb(50,50,50); color : white;} QDialog{ background-color: rgb(80,80,80)} ")
    
    def getInputs(self):
        return (self.lista_puertos.currentText(), self.checkbox_canales.isChecked(), self.checkbox_invertir.isChecked(), self.checkbox_VOP.isChecked())

class VOP_InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        boton_nuevoPaciente = QPushButton("Nuevo Paciente")
        boton_nuevoPaciente.setDefault(True)

        boton_mismoPaciente = QPushButton("Mismo Paciente")
        boton_mismoPaciente.setCheckable(True)

        boton_mismoPaciente.setAutoDefault(False)
        
        f_2 = QFont("Calibri", 18)
        boton_mismoPaciente.setFont(f_2)
        boton_nuevoPaciente.setFont(f_2)

        buttonBox = QDialogButtonBox(QtCore.Qt.Horizontal)
        buttonBox.addButton(boton_nuevoPaciente, QDialogButtonBox.AcceptRole)
        buttonBox.addButton(boton_mismoPaciente, QDialogButtonBox.RejectRole)

        layout = QGridLayout(self)
        
        label_VOP = QLabel("Última VOP medida: " + f"{VOP:.2f} ± {VOP_std_exp:.2f} %")

        f_1 = QFont("Calibri", 26, QFont.Bold)
        label_VOP.setFont(f_1)

        label_VOP.setStyleSheet("QLabel { color : white; }")
        
        layout.addWidget(label_VOP, 0, 0, QtCore.Qt.AlignCenter)
        
        layout.addWidget(buttonBox, 1, 0, QtCore.Qt.AlignCenter)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        self.setStyleSheet("QLabel { background-color: rgb(80,80,80); color : white; } QLineEdit { background-color: rgb(50,50,50); color : white;} QDialog{ background-color: rgb(80,80,80)} ")
        boton_nuevoPaciente.setStyleSheet("background-color: rgb(50,50,50); color: white")
        boton_mismoPaciente.setStyleSheet("background-color: rgb(50,50,50); color: white")

    def getInputs(self):
        return (self.name.text(), self.age.text(), self.dist_cf.text(), self.PAS.text(), self.PAD.text())

class Window(QMainWindow):

    def __init__(self):
        super().__init__()
 
        #Widgets
        self.timer_FPS = 0
        self.timer_VOP = 0

        self.label_paciente = 0

        self.VOP_LineEdit = 0
    
        self.boton_freeze = 0
        self.boton_grabar = 0
        self.boton_paciente = 0
        
        self.plot_RED = 0
        self.plot_IR = 0
        self.plot_ECG = 0
        self.canvas_RED = 0
        self.canvas_IR = 0
        self.canvas_ECG = 0

        #Variables de configuracion
        self.inversion_canales = False
        self.ECG_activo = True
        self.puertoSeleccionado = "Seleccionar Puerto"
        self.VOP_continua = False

        # setting title
        self.setWindowTitle("GIBIO uFisio - Fotopletismografo (RED - IR)")
 
        # setting geometry
        self.setGeometry(100, 100, 1000, 700)
        
        if dark_mode: 
            self.setStyleSheet("background-color: rgb(20,20,20); color:rgb(255,255,255)")
        else:
            self.setStyleSheet("background-color: rgb(232,232,232); color:rgb(0,0,0)")
        
        
        # icon
        #icon = QIcon("skin.png")
 
        # setting icon to the window
        #self.setWindowIcon(icon)        
 
        # calling method
        self.UiComponents()
 
        # showing all the widgets
        
        self.setWindowState(QtCore.Qt.WindowMaximized)
        self.show()
        
        self.timer_FPS = QTimer()
        self.timer_FPS.timeout.connect(self.plot)
        
        self.timer_VOP = QTimer()
        self.timer_VOP.timeout.connect(self.Calculo_VOP)

 
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

        #Colores para todos los botones
        if dark_mode:
            fondo = "rgb(100,100,100)"
            letras_enabled = "rgb(255,255,255)" 
            letras_disabled =  "rgb(150,150,150)"
            
        else:
            fondo = "rgb(200,200,200)"
            letras_enabled = "rgb(0,0,0)" 
            letras_disabled =  "rgb(150,150,150)"

        fuenteGrande = QFont("Calibri", 16, QFont.Bold)

        # 1-Label Paciente
        self.label_paciente = QLabel("Paciente: -")
        #self.label_paciente.setStyleSheet("QLabel { color : white; }")
        self.label_paciente.setFont(fuenteGrande)

        layout.addWidget(self.label_paciente, 0, 0, QtCore.Qt.AlignLeft)
        
        # 2-Botón PACIENTE
        self.boton_paciente = QPushButton("Paciente")
        self.boton_paciente.clicked.connect(self.Ingreso_Paciente)
        
        layout.addWidget(self.boton_paciente, 0, 1, QtCore.Qt.AlignRight)
        
        self.boton_paciente.setStyleSheet(":enabled { color: " + letras_enabled + "; background-color: " + fondo + " } :disabled { color: " + letras_disabled + "; background-color: " + fondo + " }")

        # 3-Menu de configuracion
        self.boton_config = QPushButton("Menú")
        self.boton_config.clicked.connect(self.Menu_Config)
        self.boton_config.setEnabled(False)
        
        layout.addWidget(self.boton_config, 0, 2)
        
        self.boton_config.setStyleSheet(":enabled { color: " + letras_enabled + "; background-color: " + fondo + " } :disabled { color: " + letras_disabled + "; background-color: " + fondo + " }")
        
        # 4-Velocidad de propagacion (Label y line edit)
        label_VOP = QLabel("VOP estimada: ")
        label_VOP.setFont(fuenteGrande)
        #label_VOP.setStyleSheet("QLabel { color : white; }")
        layout.addWidget(label_VOP, 0, 3, QtCore.Qt.AlignRight)
        
        self.VOP_LineEdit = QLineEdit()
        #self.VOP_LineEdit.setStyleSheet("QLineEdit { color : white; }")
        self.VOP_LineEdit.setReadOnly(True)
        self.VOP_LineEdit.setFont(fuenteGrande)
        self.VOP_LineEdit.setMaximumWidth(200)
        
        layout.addWidget(self.VOP_LineEdit, 0, 4, QtCore.Qt.AlignLeft)
        
        # 5-Botón Freeze
        self.boton_freeze = QPushButton("Graficar")
        self.boton_freeze.setEnabled(False)
        self.boton_freeze.clicked.connect(self.Freeze)
        
        self.boton_freeze.setStyleSheet(":enabled { color: " + letras_enabled + "; background-color: " + fondo + " } :disabled { color: " + letras_disabled + "; background-color: " + fondo + " }");
        
        layout.addWidget(self.boton_freeze, 0, 5)
        
        # 6-Botón Grabar
        self.boton_grabar = QPushButton("Iniciar REC")
        self.boton_grabar.setEnabled(False)
        self.boton_grabar.clicked.connect(self.Grabar)
        
        self.boton_grabar.setStyleSheet(":enabled { color: " + letras_enabled + "; background-color: " + fondo + " } :disabled { color: " + letras_disabled + "; background-color: " + fondo + " }");
        
        layout.addWidget(self.boton_grabar, 0, 6)

        
        # 7-Gráficos

        #Colores de fondo y texto
        if dark_mode:
            pg.setConfigOption('background', pg.mkColor(20,20,20))
            pg.setConfigOption('foreground', 'w')
        else:
            pg.setConfigOption('background', pg.mkColor(232,232,232))
            pg.setConfigOption('foreground', 'black')
        # creating a graph item
        self.canvas_RED = pg.PlotWidget(title="Sensor Fisiológico 1")
        self.canvas_IR = pg.PlotWidget(title="Sensor Fisiológico 2")
        self.canvas_ECG = pg.PlotWidget(title="Derivación Electrocardiográfica")
        
        # plot window goes on right side, spanning 11 rows
        layout.addWidget(self.canvas_RED, 2, 0, 2, -1)
        layout.addWidget(self.canvas_IR, 4, 0, 2, -1)
        layout.addWidget(self.canvas_ECG, 6, 0, 3, -1)
        
        self.plot_RED = self.canvas_RED.plot(pen=pg.mkPen(color = (255,0,0), width = 3))
        if dark_mode:
            self.plot_IR = self.canvas_IR.plot(pen=pg.mkPen(color = (255,255,0), width = 3))
        else:
            self.plot_IR = self.canvas_IR.plot(pen=pg.mkPen(color = (0,0,255), width = 3))
        self.plot_ECG = self.canvas_ECG.plot(pen=pg.mkPen(color = (34,177,76), width = 3))

        self.canvas_RED.showGrid(x=True, y=True, alpha=0.5)
        self.canvas_IR.showGrid(x=True, y=True, alpha=0.5)
        self.canvas_ECG.showGrid(x=True, y=True, alpha=0.5)

        # setting this awidget as central widget of the main window
        self.setCentralWidget(widget)

    #Slot Para iniciar/pausar grabacion con barra espaciadora  
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Space:
            if cond_rec == False:
                self.Freeze()
            else:
                self.Grabar()
            
    @QtCore.pyqtSlot()
    def plot(self):
        global decimacion, fs
        while data_modif == True:
            continue
        
        ventana_temporal = int(3*(fs/decimacion))
        
        if len(draw_tiempo) < ventana_temporal:    #150 muestras equivale a 3 segundos (fs = 1000hz y decimacion = 20muestras => 1000/20 = 50muestras/seg)
            window.plot_RED.setData(draw_tiempo, draw_RED)
            window.plot_IR.setData(draw_tiempo, draw_IR)
            window.plot_ECG.setData(draw_tiempo, draw_ECG)
        else:
            if tiempo_medido >= 25:    #A partir de los 25 segundos se arranca el timer que calcula cada 5 segundos el VOP (con una ventana de 20 segundos)
                if pacienteIngresado:
                    if window.timer_VOP.isActive() == False and window.VOP_continua == True:
                        print("Activando Timer VOP")
                        window.timer_VOP.start(5000)
                    elif window.timer_VOP.isActive() == True and window.VOP_continua == False:
                        print("Desactivando Timer VOP")
                        window.timer_VOP.stop()

            window.plot_RED.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_RED[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
            window.plot_IR.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_IR[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
            window.plot_ECG.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_ECG[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
    
    @QtCore.pyqtSlot()
    def Ingreso_Paciente (self):
        global pacienteIngresado,window,draw_ECG,datos_IR,draw_RED,draw_tiempo,raw_ECG,raw_IR,raw_RED,tiempo_medido, pausarThread, threadPausado
        
        pacienteIngresado = Formulario_Paciente(self)
        
        if pacienteIngresado:
            # window.timer_VOP.stop()
            
            # pausarThread = True
            
            # while threadPausado == False:
                # continue
            
            window.label_paciente.setText("Paciente: " + paciente[0] + ", " + paciente[1] + " años")   #Aparece el nombre del paciente en la ventana

            self.boton_config.setEnabled(True)  #Habilito el botón para abrir el menú y configurar luego el puerto
            
            # tiempo_inicio = time.time()
            # tiempo_medido = 0
            
            # draw_tiempo = np.resize(draw_tiempo, 0)
            # draw_RED = np.resize(draw_RED, 0)
            # #draw_IR = np.resize(draw_IR, 0)
            # draw_ECG = np.resize(draw_ECG, 0)
            
            # raw_RED = np.resize(raw_RED, 0)
            # raw_IR = np.resize(raw_IR, 0)
            # raw_ECG = np.resize(raw_ECG, 0)            
            
            # pausarThread = False
    
    @QtCore.pyqtSlot()
    def Menu_Config (self):
        dlg = Config_InputDialog(parent = self)
        
        dlg.setWindowTitle("Configuración")

        dlg.lista_puertos.setCurrentText(self.puertoSeleccionado)
        dlg.checkbox_invertir.setChecked(self.inversion_canales)
        dlg.checkbox_canales.setChecked(self.ECG_activo)
        dlg.checkbox_VOP.setChecked(self.VOP_continua)

        dlg.resize(500,200)

        if dlg.exec_():
            puertoAnterior = self.puertoSeleccionado
        
            self.puertoSeleccionado, self.ECG_activo, self.inversion_canales, self.VOP_continua = dlg.getInputs()

        
            if self.puertoSeleccionado != "Seleccionar Puerto" and puertoAnterior != self.puertoSeleccionado:
                conexion_serie(self.puertoSeleccionado)

        else:
            return False
            
    @QtCore.pyqtSlot()
    def Freeze (self):
        global window
        if window.boton_freeze.text() == 'Graficar':
            window.timer_FPS.start(int(1000/FPS_USUARIO)) #FPS definido por usuario
            window.boton_freeze.setText('Congelar')

        elif window.boton_freeze.text() == 'Congelar':
            window.timer_FPS.stop()
            window.boton_freeze.setText('Graficar')
            window.Calculo_VOP()
                
    @QtCore.pyqtSlot()
    def Grabar (self):
        global cond_rec, datos_RED, datos_IR, datos_ECG,window

        if cond_rec == False:   #Iniciar grabación

            self.boton_grabar.setText("Terminar REC")

            #Si están pausados los gráficos, se comienza a graficar para ver qué se está grabando (caso inusual)
            if window.boton_freeze.text() == 'Graficar':
                window.timer_FPS.start(int(1000/FPS_USUARIO)) #FPS definido por usuario
                window.boton_freeze.setText('Congelar')
            
            window.boton_freeze.setEnabled(False)   #Desactivo el botón para que no se pueda pausar en el medio de una grabación
            
            cond_rec = True
        
        else:                   #Terminar grabación

            cond_rec = False

            #Además de terminar la grabación se frenan los gráficos
            if window.boton_freeze.text() == 'Congelar':
                window.timer_FPS.stop()
                window.boton_freeze.setText('Graficar')

            window.boton_freeze.setEnabled(True)

            self.boton_grabar.setText("Iniciar REC")

            os.makedirs("./Mediciones", exist_ok=True) #Creo la carpeta Mediciones si no existe

            mediciones = open("./Mediciones/Medicion_" + paciente[0] + ".txt",'w')
            window.label_paciente.setText("Paciente: " + paciente[0] + ", " + paciente[1] + " años")
            mediciones.truncate(0)

            mediciones.write("Paciente: " + paciente[0] + ", " + paciente[1] + " años\n")
            mediciones.write("Distancia Carótida-Femoral:\t" + paciente[2] + " cm\n")
            mediciones.write("Presión Sistólica Braquial:\t" + paciente[3] + '\n')
            mediciones.write("Presión Diastólica Braquial:\t" + paciente[4] + '\n')
            mediciones.write("Frecuencia de muestreo:\t\t1000Hz\n\n")

            mediciones.write("Sensor 1\tSensor 2\tECG\n")

            for i in range(len(datos_RED)):
                mediciones.write(str(int(datos_RED[i])) +'\t\t'+ str(int(datos_IR[i])) +'\t\t'+ str(int(datos_ECG[i])) +'\n')
            mediciones.close()
            
            datos_RED = np.resize(datos_RED, 0)
            datos_IR = np.resize(datos_IR, 0)
            datos_ECG = np.resize(datos_ECG, 0)

            #Ventana que informa VOP y pregunta si se sigue con otro paciente o el mismo
            dlg = VOP_InputDialog(self)
            dlg.setWindowTitle("VOP Medida")        
            dlg.resize(700,300)
                
            if dlg.exec_():
                self.Ingreso_Paciente()
    
    @QtCore.pyqtSlot()
    def Calculo_VOP(self):
        global paciente, raw_RED, raw_IR, fs, VOP, VOP_std_exp

        # Just a list of the arteries where signals were taken from
        aloc = ['carotid', 'femoral']
        # Example with subject aged 25 with 61 cm between carotid and femoral
        # Data has 1000Hz of sampling frequency
        data = {'age': int(paciente[1]), 'dist_cf': int(paciente[2]), 'PAS': int(paciente[3]), 'PAD': int(paciente[4])}
        
        analisis_paciente = MA(aloc, data, fs=fs)
        
        analisis_paciente.load_signals((raw_RED, raw_IR))
        
        analisis_paciente.filter_signals()
        
        analisis_paciente.calibrate_signals(adj=1)
        
        analisis_paciente.init_signals()
        
        analisis_paciente.get_PTT()
        
        analisis_paciente.get_PWV()

        VOP = analisis_paciente.params['PWVcf_stats']['mean']
        VOP_std_exp = 2.1*analisis_paciente.params['PWVcf_stats']['std']/VOP *100

        self.VOP_LineEdit.setText(f"{VOP:.2f} ± {VOP_std_exp:.2f} %")      

#TESTEO DE FORMATO DE STRING
#Solo acepta NOMBRE_APELLIDO
def FormatoCorrecto (paciente):

    #1° Chequeo de nombre y apellido
    
    nombreApellido = paciente[0]    

    if nombreApellido[0].isupper():
        
        for i in range(1,len(nombreApellido)):
            
            if not(nombreApellido[i].isupper()):
                
                if nombreApellido[i] == '_':
                    break
                
                else:
                    return -1
        
        if i == len(nombreApellido)-1:
            return -1
        
        for i in range(i + 1, len(nombreApellido)):
            
            if not(nombreApellido[i].isupper()):
                return -1    
    else:
        return -1
    
    #2° Chequeo que los otros datos sean todos números
    
    if not (paciente[1].isnumeric() and paciente[2].isnumeric() and paciente[3].isnumeric() and paciente[4].isnumeric()):
        return -2
    
    else :
        return True

def Formulario_Paciente (parent=None):
    global paciente
    
    while (True):
    
        dlg = Patient_InputDialog(parent)
        dlg.setWindowTitle("Ingreso de Paciente")
        
        dlg.name.setText(paciente[0])
        dlg.age.setText(paciente[1])
        dlg.dist_cf.setText(paciente[2])
        dlg.PAS.setText(paciente[3])
        dlg.PAD.setText(paciente[4])
        
        dlg.resize(400,100)
        
    
        if dlg.exec_():
            paciente = dlg.getInputs()
            
            resultado = FormatoCorrecto(paciente)
            
            if resultado == True:
                return True
            else:
                if resultado == -1 :
                    msgBox = QMessageBox()
                    msgBox.setText("Formato de nombre y apellido incorrecto\nVuelva a ingresarlo.")
                    msgBox.setStyleSheet("QLabel { color : white; } QMessageBox {background-color: rgb(100,100,100);}")
                    msgBox.setWindowTitle("Error de Formato")
                    msgBox.exec()
                elif resultado == -2:
                    msgBox = QMessageBox()
                    msgBox.setText("Alguno(s) de los datos numéricos es incorrecto\nVuelva a ingresarlo(s).")
                    msgBox.setStyleSheet("QLabel { color : white; } QMessageBox {background-color: rgb(100,100,100);}")
                    msgBox.setWindowTitle("Error datos numéricos")
                    msgBox.exec()
        else:
            return False

# preallocate empty array and assign slice by chrisaycock
def shift_array(arr, num, fill_value=np.nan):
    result = np.empty_like(arr)
    if num > 0:
        result[:num] = fill_value
        result[num:] = arr[:-num]
    elif num < 0:
        result[num:] = fill_value
        result[:num] = arr[-num:]
    else:
        result[:] = arr
    return result

# create pyqt5 app
App = QApplication(sys.argv)
V = QFont("Calibri", 12)
App.setFont(V)
# create the instance of our Window
window = Window()

# start the app
sys.exit(App.exec())