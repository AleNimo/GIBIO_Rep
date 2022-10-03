# -*- coding: utf-8 -*-
"""
Created on Tue May  3 15:26:18 2022

@author: Alejo
"""

# importing Qt widgets
from PyQt5 import QtCore
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

tiempo_medido = 0

tiempo_inicio = 0

paciente = np.array(["NOMBRE_APELLIDO", '-', '-', '-', '-'])

pacienteIngresado = False

decimacion = 20

pausarThread = False

threadPausado = False

T1 = 0

VOP = 0

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
                sample_RED = int.from_bytes(s.read(2), "big")   #los primeros dos bytes son led rojo
                sample_IR = int.from_bytes(s.read(2), "big")    #los siguientes dos bytes son led infrarojo
                sample_ECG = int.from_bytes(s.read(2), "big")    #los siguientes dos bytes son led infrarojo
                
                if window.checkbox_invertir.isChecked():
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

def conexion_serie(lista_puertos): 
    global cond, s, Thread_Timeado, data_on, window, T1, draw_RED, draw_IR, draw_ECG, raw_RED, raw_IR, raw_ECG, tiempo_inicio, draw_tiempo, tiempo_medido
    puerto = lista_puertos.currentText()
    if puerto != "":
        
        if cond == False:   #si el boton no estaba presionado antes ingresa
            
            try:
                s = sr.Serial(puerto.split()[0], 115200)    #intenta abrir el puerto
            except sr.SerialException:
                #m_box.showerror('Error','Puerto serie ya abierto')  #en caso de fallar sale cartel de error
                return None
            # if s.isOpen():
            #     s.close()
            # s.open()
            
            s.reset_input_buffer()  #limpia buffer del puerto serie
            cond = True
            window.boton_start.setText("Cerrar Puerto") #cambia el texto del boton

            T1 = Thread_Lectura()#inicia thread con la funcion de lectura
            T1.start()
            window.timer_FPS.start(int(1000/FPS_USUARIO)) #FPS definido por usuario
            
            tiempo_inicio = time.time()
            
            window.boton_grabar_start.setEnabled(True)
        else:
            if(cond_rec==False):
                cond = False
                window.boton_start.setText("Abrir Puerto") #cambia el texto del boton
                
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
                
                window.boton_grabar_start.setEnabled(False)
                window.boton_grabar_stop.setEnabled(False)
            else:
            
                
                msgBox = QMessageBox()
                msgBox.setStyleSheet("QLabel { color : white; } QMessageBox {background-color: rgb(100,100,100);}")
                msgBox.setWindowTitle("Error Al Cerrar Puerto")
                msgBox.setText("Pause la grabacion antes de cerrar el puerto.")
                msgBox.exec()
                

            

class ComboBox(QComboBox):
    
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

class VOP_InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        boton_nuevoPaciente = QPushButton("Nuevo Paciente")
        boton_nuevoPaciente.setDefault(True)

        boton_mismoPaciente = QPushButton("Mismo Paciente")
        boton_mismoPaciente.setCheckable(True)

        boton_mismoPaciente.setAutoDefault(False)

        buttonBox = QDialogButtonBox(QtCore.Qt.Horizontal)
        buttonBox.addButton(boton_nuevoPaciente, QDialogButtonBox.AcceptRole)
        buttonBox.addButton(boton_mismoPaciente, QDialogButtonBox.RejectRole)

        layout = QGridLayout(self)
        
        label_VOP = QLabel("Última VOP medida: " + f"{VOP:.2f}")

        f = QFont("Calibri", 18, QFont.Bold)
        label_VOP.setFont(f)

        label_VOP.setStyleSheet("QLabel { color : white; }")
        
        layout.addWidget(label_VOP, 0, 0, QtCore.Qt.AlignCenter)
        
        layout.addWidget(buttonBox, 1, 0, QtCore.Qt.AlignCenter)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        self.setStyleSheet("QLabel { background-color: rgb(80,80,80); color : white; } QLineEdit { background-color: rgb(50,50,50); color : white;} QDialog{ background-color: rgb(80,80,80)} ")
        boton_nuevoPaciente.setStyleSheet("background-color: rgb(80,80,80); color: white")
        boton_mismoPaciente.setStyleSheet("background-color: rgb(80,80,80); color: white")

    def getInputs(self):
        return (self.name.text(), self.age.text(), self.dist_cf.text(), self.PAS.text(), self.PAD.text())


class Window(QMainWindow):
 
    timer_FPS = 0
    timer_VOP = 0
    
    #label_fps = 0
    label_paciente = 0
    
    #FPS_LineEdit = 0
    VOP_LineEdit = 0
    
    lista_puertos = 0
   
    boton_start = 0
    boton_grabar_start = 0
    boton_grabar_stop = 0
    boton_paciente = 0
    
    checkbox_invertir = 0
    
    plot_RED = 0
    plot_IR = 0
    plot_ECG = 0
    canvas_RED = 0
    canvas_IR = 0
    canvas_ECG = 0
    
    
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

        
        # # FPS
        # self.label_fps = QLabel("FPS:")
        # self.label_fps.setStyleSheet("QLabel { color : white; }")
        
        # layout.addWidget(self.label_fps, 0, 0, QtCore.Qt.AlignRight)

        # self.FPS_LineEdit = QLineEdit()
        # self.FPS_LineEdit.setStyleSheet("QLineEdit { color : white; }")
        # self.FPS_LineEdit.textChanged[str].connect(self.onChanged)
        
        # self.FPS_LineEdit.setMaximumWidth(130)
        
        # layout.addWidget(self.FPS_LineEdit, 0, 1, QtCore.Qt.AlignLeft)
        
        # self.FPS_LineEdit.setText("24")
        
         # Label Paciente
        self.label_paciente = QLabel("Paciente: -")
        self.label_paciente.setStyleSheet("QLabel { color : white; }")
        
        layout.addWidget(self.label_paciente, 0, 0, QtCore.Qt.AlignRight)
 
        
        # Boton PACIENTE
        self.boton_paciente = QPushButton("Paciente")
        self.boton_paciente.clicked.connect(self.Ingreso_Paciente)
        
        layout.addWidget(self.boton_paciente, 0, 2, QtCore.Qt.AlignRight)
        
        self.boton_paciente.setStyleSheet("background-color: rgb(100,100,100);")

        
        # Velocidad de propagacion
        label_VOP = QLabel("VOP de últimos 20 segundos: ")
        label_VOP.setStyleSheet("QLabel { color : white; }")
        layout.addWidget(label_VOP, 0, 3, QtCore.Qt.AlignRight)
        
        self.VOP_LineEdit = QLineEdit()
        self.VOP_LineEdit.setStyleSheet("QLineEdit { color : white; }")
        self.VOP_LineEdit.setReadOnly(True)
        
        
        self.VOP_LineEdit.setMaximumWidth(150)
        
        layout.addWidget(self.VOP_LineEdit, 0, 4, QtCore.Qt.AlignLeft)
        
        # Checkbox para inversion de canales
        self.checkbox_invertir = QCheckBox("Invertir")
        self.checkbox_invertir.setTristate(False)
        self.checkbox_invertir.setChecked(True) #Comienza invertido
        self.checkbox_invertir.setStyleSheet("QCheckBox { color : white; }")
        layout.addWidget(self.checkbox_invertir, 0, 5, QtCore.Qt.AlignRight)

        # PUERTO SERIE
        label = QLabel("Puerto Serie:")
        label.setStyleSheet("QLabel { color : white; }")

        layout.addWidget(label, 0, 6, QtCore.Qt.AlignRight)


        self.lista_puertos = ComboBox()
        self.lista_puertos.setMinimumWidth(130)
        self.lista_puertos.setStyleSheet("background-color: rgb(100,100,100);")
        self.lista_puertos.addItem("Seleccionar Puerto")
        
        layout.addWidget(self.lista_puertos, 0, 7, QtCore.Qt.AlignLeft)
        
        
        # Botón Abrir Puerto
        self.boton_start = QPushButton("Abrir Puerto")
        self.boton_start.clicked.connect(lambda:conexion_serie(self.lista_puertos))
        self.boton_start.setEnabled(False)
        
        self.boton_start.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_start, 0, 8)
        
        # Botón Grabar Start
        self.boton_grabar_start = QPushButton("Iniciar REC")
        self.boton_grabar_start.setEnabled(False)
        self.boton_grabar_start.clicked.connect(self.Grabar_Start)
        
        self.boton_grabar_start.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_grabar_start, 0, 9)
        
        # Botón Grabar Stop
        self.boton_grabar_stop = QPushButton("Pausar REC")
        self.boton_grabar_stop.setEnabled(False)
        self.boton_grabar_stop.clicked.connect(self.Grabar_Stop)
        
        self.boton_grabar_stop.setStyleSheet("background-color: rgb(100,100,100);")
        
        layout.addWidget(self.boton_grabar_stop, 0, 10)
        
        # Gráficos

        #Colores de fondo y texto
        pg.setConfigOption('background', pg.mkColor(20,20,20))
        pg.setConfigOption('foreground', 'w')
    
        # creating a graph item
        self.canvas_RED = pg.PlotWidget(title="RED")
        self.canvas_IR = pg.PlotWidget(title="IR")
        self.canvas_ECG = pg.PlotWidget(title="ECG")
        
        # plot window goes on right side, spanning 11 rows
        layout.addWidget(self.canvas_RED, 1, 0, 1, -1)
        layout.addWidget(self.canvas_IR, 3, 0, 1, -1)
        layout.addWidget(self.canvas_ECG, 5, 0, 2, -1)
        
        self.plot_RED = self.canvas_RED.plot(pen=pg.mkPen(color = (255,0,0), width = 3))
        self.plot_IR = self.canvas_IR.plot(pen=pg.mkPen(color = (255,255,0), width = 3))
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
                self.Grabar_Start()
            else:
                self.Grabar_Stop()
            
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
                    if window.timer_VOP.isActive() == False:
                        print("Activando TIMER")
                        window.timer_VOP.start(5000)
            
            window.plot_RED.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_RED[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
            window.plot_IR.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_IR[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
            window.plot_ECG.setData(draw_tiempo[(len(draw_tiempo)-1)-(ventana_temporal-1):len(draw_tiempo)-1], draw_ECG[len(draw_tiempo)-1-(ventana_temporal-1):len(draw_tiempo)-1])
            
    

    # def onChanged(self, text):
        # global FPS_USUARIO
        # if text.isnumeric():
            # FPS_USUARIO = int(str(text))
            # if cond == True:
                # window.timer_FPS.start(int(1000/FPS_USUARIO)) #Para que se actualicen los FPS mientras imprime
        # else:
            # print("FPS INVALIDO")
    
    @QtCore.pyqtSlot()
    def Ingreso_Paciente (self):
        global pacienteIngresado,window,draw_ECG,datos_IR,draw_RED,draw_tiempo,raw_ECG,raw_IR,raw_RED,tiempo_medido, pausarThread, threadPausado
        
        pacienteIngresado = Formulario_Paciente(self)
        
        if pacienteIngresado:
            # window.timer_VOP.stop()
            
            # pausarThread = True
            
            # while threadPausado == False:
                # continue
            
            window.label_paciente.setText("Paciente: " + paciente[0])   #Aparece el nombre del paciente en la ventana

            self.boton_start.setEnabled(True)  #Habilito el botón para abrir el puerto
            
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
    def Grabar_Start (self):
        global cond_rec, datos_RED, datos_IR, datos_ECG,window
        

        self.boton_grabar_start.setEnabled(False)
        self.boton_grabar_stop.setEnabled(True)
            
        cond_rec = True
            
                
    @QtCore.pyqtSlot()
    def Grabar_Stop (self):
        global cond_rec, datos_RED, datos_IR, datos_ECG,window
                    
        cond_rec = False
        self.boton_grabar_start.setEnabled(True)
        self.boton_grabar_stop.setEnabled(False)

        os.makedirs("./Mediciones", exist_ok=True) #Creo la carpeta Mediciones si no existe

        mediciones = open("./Mediciones/Medicion_" + paciente[0] + ".txt",'w')
        window.label_paciente.setText("Paciente: " + paciente[0])
        mediciones.truncate(0)

        for i in range(len(datos_RED)):
            mediciones.write(str(int(datos_RED[i])) +' '+ str(int(datos_IR[i])) +' '+ str(int(datos_ECG[i])) +'\n')
        mediciones.close()
        
        datos_RED = np.resize(datos_RED, 0)
        datos_IR = np.resize(datos_IR, 0)
        datos_ECG = np.resize(datos_ECG, 0)

        #Ventana que informa VOP y pregunta si se sigue con otro paciente o el mismo
        dlg = VOP_InputDialog(self)
        dlg.setWindowTitle("VOP Medida")        
        dlg.resize(400,100)
            
        if dlg.exec_():
            self.Ingreso_Paciente()
    
    @QtCore.pyqtSlot()
    def Calculo_VOP(self):
        global paciente, raw_RED, raw_IR, fs, VOP
        
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

        self.VOP_LineEdit.setText(f"{VOP:.2f}")
            
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
        dlg.setWindowTitle("Grabación")
        
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