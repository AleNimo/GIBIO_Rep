import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from math import ceil
from scipy.signal import butter, filtfilt
from scipy.io import loadmat

import Deep_Delineator_Code.Deep_Delineator as DD

# pasos:
# 1- leer csv o mat - OK
# 2- filtrar señal - OK
# 3- calibrar señal con presión braquial - OK
# 4- delineador - OK
# 5- sincronizador de señales - OK
# 6- feature extraction - obtención de parámetros - OK (WIP futuro)
# 6.1- obtener ptt - OK
# 6.2- obtener vop - OK
# (por el momento esos solos)


class Morphology_Analyzer():
    def __init__(self, aloc, data, fs=500):
        self.params = {}
        self.signals = []
        self.aloc = aloc
        self.patinfo = data
        self.fs = fs
    
    def load_signals_from_file(self, path, type, col_names=None, sep=' '):
        if type == 'csv':

            df = pd.read_csv(path, 
                sep=sep,
                names=col_names)

            for i_s in range(len(self.aloc)):
                self.signals.append(df[self.aloc[i_s]].values)

        elif type == 'mat':

            mat = loadmat(path)

            for nsig in self.aloc:
                aux = np.concatenate([np.array(i) for i in mat[nsig]])
                self.signals.append(aux)
    
        else:
            print("Type not supported. Either csv or mat file")

    def load_signals(self, sigs):
        self.signals = sigs

    def __set_model_delineator(self, model_type='U_TCN'):
        self.model_type = model_type
        self.model = DD.load_checkpoint('Deep_Delineator_Code/'+self.model_type+'.pt')

    def __get_detections(self):
        self.__set_model_delineator()
        self.detections = self.model.pred_from_numpy(self.signals, s_f=self.fs)

    def __get_beats_shape(self):
        for artery in self.aloc:
            idx = self.aloc.index(artery)
            beats_shape = np.shape(self.detections[idx]['original']['beats_fips'])
            print(f'There are {beats_shape[0]} complete beats in {artery} artery')

    def __plot_detections(self, artery):
        idx = self.aloc.index(artery)
        sf_plot = self.detections[idx]['original']['s_f']
        signal = self.detections[idx]['original']['signal']
        peak_idx = self.detections[idx]['original']['peaks']
        onset_idx = self.detections[idx]['original']['onset']
        dn_idx = self.detections[idx]['original']['dn']
        peak_val = signal[peak_idx]
        onset_val = signal[onset_idx]
        dn_val = signal[dn_idx]
        peak_time = peak_idx/sf_plot
        onset_time = onset_idx/sf_plot
        dn_time = dn_idx/sf_plot
        t_vec = np.arange(0, len(signal))/sf_plot
        #Plots
        fig, ax0 = plt.subplots(nrows=1, ncols=1, figsize=(15,5))
        ax0.plot(t_vec, signal, c='black', alpha=0.5, label='signal')
        ax0.scatter(peak_time, peak_val, c='r', label='Peaks')
        ax0.scatter(onset_time, onset_val, c='b', label = 'Onsets')
        ax0.scatter(dn_time, dn_val, c='g', label = 'Dicrotic Notchs')
        ax0.legend(fontsize=16)
        ax0.set_title('Detection for Change of Classes',fontsize=28)
        ax0.set_xlabel('Time [s]',fontsize=24)
        ax0.set_ylabel('Blood Pressure',fontsize=24)
        ax0.set_xlim(0,t_vec[-1])
        # explicitly the different batch analized
        for i in np.arange(0, len(signal)/sf_plot,(1024*2)/125):
            plt.axvspan(i, i+1024/125, facecolor='b', alpha=0.15)
        plt.show()

    def plot_signal(self, artery):
        idx = self.aloc.index(artery)
        signal = self.signals[idx]
        t_vec = np.arange(0, len(signal))/self.fs
        #Plots
        fig, ax0 = plt.subplots(nrows=1, ncols=1, figsize=(15,5))
        ax0.plot(t_vec, signal, c='black', alpha=0.5, label=self.aloc[idx])
        ax0.set_facecolor('xkcd:baby blue')
        ax0.set_alpha(0.15)
        ax0.legend(fontsize=16)
        ax0.set_title('Signal from '+self.aloc[idx]+' artery',fontsize=28)
        ax0.set_xlabel('Time [s]',fontsize=24)
        ax0.set_ylabel('Blood Pressure',fontsize=24)
        ax0.set_xlim(0,t_vec[-1])
        plt.show()

    def plot_all_signals(self):
        for i_s in range(len(self.aloc)):
            self.plot_signal(self.aloc[i_s])


    def __sync_signals(self):
        #Asumo que en 0 está la carótida, que se usa para sincronizar a las demás
        # Vector de control para después homogeneizar los datos
        ctrl_vec = np.full(len(self.detections[0]['original']['onset'])-1, True)
        #-1 porque siempre se descarta el último latido 

        #aux de cont original
        foot0 = [[] for x in range(len(self.aloc))]
        dn0 = [[] for x in range(len(self.aloc))]
        syst0 = [[] for x in range(len(self.aloc))]

        #copio contenido original
        for i in range(len(self.aloc)):
            foot0[i] = self.detections[i]['original']['onset']
            syst0[i] = self.detections[i]['original']['peaks']
            dn0[i] = self.detections[i]['original']['dn']

        #nuevo sincronizado
        sync_foot = [[] for x in range(len(self.aloc))]
        sync_dn = [[] for x in range(len(self.aloc))]
        sync_syst = [[] for x in range(len(self.aloc))]

        syst = syst0[0]
        dn = dn0[0]

        for ibeats in range(len(foot0[0])-1):
            left = foot0[0][ibeats]
            right = foot0[0][ibeats+1]

            if left == 0 or right == 0:
                # no lo encontro, latido fallido
                sync_foot[0].insert(ibeats, False)
                sync_dn[0].insert(ibeats, False)
                sync_syst[0].insert(ibeats, False)
                ctrl_vec[ibeats] = False
                continue
            
            #busco el indice de sístole en el latido actual
            syst_v = syst[np.logical_and(syst>left, syst<right)]

            if syst_v.size == 0:
                dn_v = []
            else:
                # el if es porque a veces encuentra más de uno, me quedo con el de menor index
                if syst_v.size > 1 and np.all(syst_v == syst_v[0]):
                    syst_v = syst_v[0]
                #busco el dicrot notch en el latido actual y tiene que estar después del pico de sístole
                dn_v = dn[np.logical_and(dn>left, np.logical_and(dn<right, dn>syst_v))]
                if dn_v.size > 1 and np.all(dn_v == dn_v[0]):
                    dn_v = dn_v[0]

            #no encontro bien en el latido actual alguno de los dos
            if syst_v.size == 0 or dn_v.size == 0:
                sync_foot[0].insert(ibeats, False)
                sync_dn[0].insert(ibeats, False)
                sync_syst[0].insert(ibeats, False)
                ctrl_vec[ibeats] = False
                continue
            
            #los encontro, los guardo
            sync_foot[0].insert(ibeats, left)
            sync_dn[0].insert(ibeats, dn_v[0])
            sync_syst[0].insert(ibeats, syst_v[0])
            last_foot = right

        sync_foot[0] = np.array(sync_foot[0])
        sync_dn[0] = np.array(sync_dn[0])
        sync_syst[0] = np.array(sync_syst[0])

        sync_foot[0] = sync_foot[0][ctrl_vec]
        sync_dn[0] = sync_dn[0][ctrl_vec]
        sync_syst[0] = sync_syst[0][ctrl_vec]

        #### Sync
        ctrl_vec = np.full(len(sync_syst[0]), True)

        for ibeats in range(len(sync_syst[0])):
            left = syst0[0][ibeats]

            if ibeats == (len(syst0[0])-1):
                right = last_foot
            else:
                right = syst0[0][ibeats+1]
            
            for i in range(1, len(self.aloc)):
                syst = syst0[i]

                #encuentro en la otra arteria el pico de sistole en el latido actual
                logic = np.logical_and(syst > left, syst < right)
                idx = min(np.where(logic))

                if idx.size == 0:
                    # no lo encontro, latido fallido
                    sync_foot[0][ibeats] = False
                    sync_dn[0][ibeats] = False
                    sync_syst[0][ibeats] = False
                    
                    sync_foot[i].insert(ibeats, False)
                    sync_dn[i].insert(ibeats, False)
                    sync_syst[i].insert(ibeats, False)

                    ctrl_vec[ibeats] = False
                    continue

                idx = idx[0] #hay veces que encuentra más de uno

                sync_foot[i].insert(ibeats, foot0[i][idx])
                sync_dn[i].insert(ibeats, dn0[i][idx])
                sync_syst[i].insert(ibeats, syst0[i][idx])

        for i in range(len(self.aloc)):
            if i > 0:
                sync_foot[i] = np.array(sync_foot[i])
                sync_dn[i] = np.array(sync_dn[i])
                sync_syst[i] = np.array(sync_syst[i])

            sync_foot[i] = sync_foot[i][ctrl_vec]
            sync_syst[i] = sync_syst[i][ctrl_vec] 
            sync_dn[i] = sync_dn[i][ctrl_vec]

        self.last_foot = last_foot
        for i in range(len(self.aloc)):
            self.detections[i]['original']['onset'] = sync_foot[i]
            self.detections[i]['original']['peaks'] = sync_syst[i]
            self.detections[i]['original']['dn'] = sync_dn[i]
    
    def init_signals(self):
        self.__get_detections()
        self.__get_beats_shape()
        self.__sync_signals()
        
        # for i_s in range(len(self.aloc)):
        #     self.__plot_detections(artery=self.aloc[i_s])

    def get_PTT(self):
        #aux de cont original
        foot0 = [[] for x in range(len(self.aloc))]
        dn0 = [[] for x in range(len(self.aloc))]
        syst0 = [[] for x in range(len(self.aloc))]
        sig0 = [[] for x in range(len(self.aloc))]

        #copio contenido original
        for i in range(len(self.aloc)):
            sig0[i] = self.detections[i]['original']['signal']
            foot0[i] = self.detections[i]['original']['onset']
            syst0[i] = self.detections[i]['original']['peaks']
            dn0[i] = self.detections[i]['original']['dn']
        
        # PTT calculado con el método del gradiente
        #thresholds
        PTT_min = 0 #ms
        PTT_max = 0.5
        len_limit = 2*self.fs
        sd_lim = 2
        
        dt = 1/(self.fs)
        #es el mismo para todas las señales
        # SI O SI DPS DE SINCRONIZAR
        signal_len = len(self.detections[0]['original']['signal'])
        #obtengo el eje temporal
        t = np.arange(0, (signal_len-1)*dt, dt)
        #cantidad de muestras a tomar para hacer la regresión antes y dps
        #del punto max del gradiente
        npoly = ceil(0.03*self.fs)

        min_size_SysPeak = []
        min_size_foot = []

        for i_bp in range(len(self.aloc)):
            min_size_SysPeak.append(len(syst0[i_bp]))
            min_size_foot.append(len(foot0[i_bp]))

        #chequeos por las dudas
        #deberia ser len 1 porque ambos deberian ser iguales
        q_peaks = np.unique(min_size_SysPeak)
        q_foots = np.unique(min_size_foot)

        #si el len es mayor a uno, algo mal
        if (len(q_peaks)>1) or (len(q_foots)>1):
            print('Error')
            exit()

        #si son distintos, está mal
        #o sea algo mal en la sincronización
        if q_peaks != q_foots:
            print('Error')
            exit()
        
        indmaxs = []
        indmins = []
        sigs_in = []

        for i_bp in range(len(self.aloc)):
            sigs_in.append(self.detections[i_bp]['original']['signal'])

            indmaxs.append(syst0[i_bp][:q_peaks[0]])

            idx_min = []
            idx_min.append(foot0[i_bp][:q_foots[0]])
            v_min = []
            v_min.append(sig0[i_bp][idx_min[0]])
            
            min_data = [idx_min, v_min]
            indmins.append(min_data)
        
        gradins = []
        #Tang. proy
        #gradins[0] = x, gradins[1] = m (pend), gradins[2] = b, gradins[3] = v (y)
        for i_s in range(len(self.aloc)):
            gradin = []
            #puntos caracteristicos de la señal a evaluar
            s = sigs_in[i_s]
            foot_s = indmins[i_s][0][0]
            syst_s = indmaxs[i_s]

            for i_grad in range(len(syst_s)):
                idx = np.argmax(np.diff(s[foot_s[i_grad]:syst_s[i_grad]]))
                idx = idx + foot_s[i_grad]
                
                llim = idx - ((np.around((npoly+1)/2))-1)
                llim = llim.astype(int)
                hlim = idx + ((np.around((npoly+1)/2))-1)
                hlim = hlim.astype(int)

                xpoly = t[llim:hlim]
                ypoly = s[llim:hlim]
                poly = np.polyfit(xpoly, ypoly, 1)
                v = (poly[0]*t[idx])+poly[1]
                c = [idx, poly[0], poly[1], v]
                
                gradin.append(c)
            
            gradins.append(gradin)

        TT,t_foot,horint = self.__PWV_Calculator_FTF(t, sigs_in, indmaxs, indmins, gradins)

        q_struct = np.size(foot0[0])
        feat_PTT = self.__create_dict_PTT(q_struct)

        ctrl_vec = np.full(q_struct, True)

        for i_beat in range(q_struct):
            left = foot0[0][i_beat]

            if i_beat == (q_struct-1):
                right = self.last_foot
            else:
                right = foot0[0][i_beat+1]
            
            if left+len_limit < right:
                ctrl_vec[i_beat] = False
                continue
            
            abp_p1 = t_foot[0][i_beat]*self.fs
            abp_p2 = t_foot[1][i_beat]*self.fs

            if (TT[i_beat] < PTT_min) or (TT[i_beat] > PTT_max):
                ctrl_vec[i_beat] = False
                continue

            feat_PTT['left'][i_beat] = left
            feat_PTT['right'][i_beat] = right
            feat_PTT['abp_p1'][i_beat] = abp_p1
            feat_PTT['abp_p2'][i_beat] = abp_p2
            feat_PTT['PTTcf'][i_beat] = TT[i_beat]
            feat_PTT['gradins1'][i_beat] = gradins[0][i_beat]
            feat_PTT['gradins2'][i_beat] = gradins[1][i_beat]

        feat_PTT['left']  = np.array(feat_PTT['left'], dtype="object")
        feat_PTT['right']  = np.array(feat_PTT['right'], dtype="object")
        feat_PTT['abp_p1']  = np.array(feat_PTT['abp_p1'], dtype="object")
        feat_PTT['abp_p2']  = np.array(feat_PTT['abp_p2'], dtype="object")
        feat_PTT['PTTcf']  = np.array(feat_PTT['PTTcf'], dtype="object")
        feat_PTT['gradins1']  = np.array(feat_PTT['gradins1'], dtype="object")
        feat_PTT['gradins2']  = np.array(feat_PTT['gradins2'], dtype="object")

        feat_PTT['left'] = feat_PTT['left'][ctrl_vec]
        feat_PTT['right'] = feat_PTT['right'][ctrl_vec]
        feat_PTT['abp_p1'] = feat_PTT['abp_p1'][ctrl_vec]
        feat_PTT['abp_p2'] = feat_PTT['abp_p2'][ctrl_vec]
        feat_PTT['PTTcf'] = feat_PTT['PTTcf'][ctrl_vec]
        feat_PTT['gradins1'] = feat_PTT['gradins1'][ctrl_vec]
        feat_PTT['gradins2'] = feat_PTT['gradins2'][ctrl_vec]

        vals = feat_PTT['PTTcf']

        std_v = np.std(vals)
        mean_v = np.mean(vals)
        lb = mean_v - sd_lim*std_v
        ub = mean_v + sd_lim*std_v

        mean_PTT = np.mean(vals[np.logical_and(vals<ub, vals>lb)])
        std_PTT = np.std(vals[np.logical_and(vals<ub, vals>lb)])

        stats_PTT = {}
        stats_PTT['mean'] = mean_PTT
        stats_PTT['std'] = std_PTT

        self.params['PTTcf'] = feat_PTT
        self.params['PTT_stats'] = stats_PTT

    #adaptación de func de charlton en matlab
    def __PWV_Calculator_FTF(self, t, signal, indmaxs, indmins, gradins):
        horint = [[0 for x in range(len(gradins[0]))] for y in range(len(signal))]
        t_foot = [[0 for x in range(len(gradins[0]))] for y in range(len(signal))]
        ind = [[0 for x in range(len(gradins[0]))] for y in range(len(signal))]

        lin = min(len(indmaxs[0]), len(indmins[0][1][0]))
        lin = min(lin, len(gradins[0]))

        for i_s in range(len(signal)):
            for i_grad in range(len(gradins[i_s])):
                if (gradins[i_s][i_grad] != 0) or (indmins[i_s][0][0][i_grad] != 0):
                    #horizontal limits
                    centre = indmins[i_s][0][0][i_grad]
                    space = 1
                    horint[i_s][i_grad] = np.mean(signal[i_s][(centre-space):(centre+space)])
                    #locate trasnient intercept
                    t_foot[i_s][i_grad] = ((horint[i_s][i_grad] - gradins[i_s][i_grad][2])/(gradins[i_s][i_grad][1]))
                    ind[i_s][i_grad] = gradins[i_s][i_grad][0]

        TT = np.array(t_foot[0]) - np.array(t_foot[1])
        if(np.median(TT)<0):
            TT = -TT
        
        return TT,t_foot,horint
    
    def __create_dict_PTT(self, q_struct):
        feat_PTT = {}
        feat_PTT['left'] = [[] for x in range(q_struct)]
        feat_PTT['right'] = [[] for x in range(q_struct)]
        feat_PTT['abp_p1'] = [[] for x in range(q_struct)]
        feat_PTT['abp_p2'] = [[] for x in range(q_struct)]
        feat_PTT['PTTcf'] = [[] for x in range(q_struct)]
        feat_PTT['gradins1'] = [[] for x in range(q_struct)]
        feat_PTT['gradins2'] = [[] for x in range(q_struct)]

        return feat_PTT

    def get_PWV(self):
        #SALVI CAP 2.2
        # Age_corr_dist[cm] = (Dist_cf[cm] * 0.8) + (0.1*(age-50))
        q_struct = len(self.params['PTTcf']['PTTcf'])

        feat_PWVcf = {}
        feat_PWVcf['PWVcf'] = [[] for y in range(q_struct)]

        if (self.patinfo['dist_cf'] < 1):
            #está en m la paso a cm
            dist = self.patinfo['dist_cf']/100
        else:
            #está en cm
            dist = self.patinfo['dist_cf']
            self.patinfo['dist_cf'] = self.patinfo['dist_cf']/100 #asi queda guardada en m 

        # Age corrected distance, in meters
        corr_dist = ((dist * 0.8) + (0.1 * (self.patinfo['age']-50)))/100

        self.patinfo['corr_dist_cf'] = corr_dist

        for i_beat in range(q_struct):
            feat_PWVcf['PWVcf'][i_beat] = corr_dist/self.params['PTTcf']['PTTcf'][i_beat]

        vals = np.array(feat_PWVcf['PWVcf'])

        std_v = np.std(vals)
        mean_v = np.mean(vals)
        sd_lim = 2 #borrar dps
        lb = mean_v - sd_lim*std_v
        ub = mean_v + sd_lim*std_v

        logic = np.logical_and(vals<ub, vals>lb)
        mean_PWVcf = np.mean(vals[logic])
        std_PWVcf = np.std(vals[logic])

        stats_PWVcf = {}
        stats_PWVcf['mean'] = mean_PWVcf
        stats_PWVcf['std'] = std_PWVcf

        self.params['PWVcf'] = feat_PWVcf
        self.params['PWVcf_stats'] = stats_PWVcf

    def calibrate_signals(self, adj, val1 = 0, val2 = 0):
        qsigs = len(self.aloc)
        sigs_cal = [[] for x in range(qsigs)]

        for i_s in range(qsigs):
            sig = self.signals[i_s]
            
            if adj == 1:
                #Ajuste por valor máximo y mínimo
                if val1 == 0 and val2 == 0:
                    val1 = max(sig)
                    val2 = min(sig)
                vals = [val1, val2]
                mags = [self.patinfo['PAS'], self.patinfo['PAD']]
                # señal calibrada: y-y0 = m*(x-x0)
                pend = np.diff(mags)/np.diff(vals)
                sigs_cal[i_s] = (pend * (sig - val1)) + self.patinfo['PAS']
            elif adj == 2:
                #Ajuste por valor medio y mínimo constante
                #resta el mín a la media para que al sumar al final el mín quede a la media solicitada
                sig_aux = sig - min(sig)
                vmed = val1 - self.patinfo['PAS']
                sigs_cal[i_s] = (sig_aux/np.mean(sig_aux))*vmed
                sigs_cal[i_s] = sigs_cal[i_s] + self.patinfo['PAS']
            else:
                print("Error in adj value. Should be either 1 (max/min) or 2 (median val)")
        
        self.signals = sigs_cal

    def filter_signals(self):
        [b, a] = butter(3, [0.5*2/self.fs,20*2/self.fs], 'bandpass')

        sigs = [self.signals[i_s] for i_s in range(len(self.aloc))]

        for i_s in range(len(self.aloc)):
            sigs[i_s] = filtfilt(b, a, sigs[i_s], padtype='odd', padlen=3*(max(len(b),len(a))-1))
        
        self.signals = sigs