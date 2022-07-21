import os
import numpy as np
import scipy.io as sio
from scipy.interpolate import interp1d
import scipy.signal
from sklearn.preprocessing import MinMaxScaler

# PyTorch
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset,DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.nn.utils import clip_grad_norm_

from tqdm.autonotebook import tqdm 

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

##############################################
# Deep_Delineator (Base Class)
##############################################
class PredictDataset(Dataset):
  def __init__(self,X,device):
    self.X = X
    self.scaler = MinMaxScaler()
    self.device = device
  def __getitem__(self, index):
    x = self.X[index]
    #x = np.reshape(np.asarray(x),(np.shape(x)[0],1))
    x = self.scaler.fit_transform(x)
    x = np.reshape(x,(1,np.shape(x)[0]))
    x = torch.from_numpy(x).float().to(self.device)
    return (x)
  def __len__(self):
    return len(self.X)

##############################################
# Deep_Delineator (Base Class)
##############################################
class Deep_Delineator_base(nn.Module):

  def predict(self, dataloader):
    pass 
  
  def pred_from_numpy(self,signal_list,s_f):
    """
    Inputs:
      signal_list (list) : list cointaining [N_signals in form of ndarray], where each
      ndarray has the shape of (samples,)

      s_f (int): sampling frecuency of the signals
    
    Return:
      detection (dict) : a dictionary containing the keys
        detection[i_r] = {
          # Prediction based on the given s_f
          'resampled':{
              'signal': analized signal acording the self.s_f of the trained model
              'predictions': classes predictions of the model,
              'onset': onset indexes,
              'peaks': peak indexes,
              'dn': dn indexes,
              'beats_fips': completed beat in [N° beat, start|peak|dn|end ] order
              'artifacts': list of artifacts,
              'rs_f': self.f_s}
          'original':{
            'signal': the analized signal resampled to the given 's_f',
            'predictions': interpolated prediction
            'onset': onset indexes to the given 's_f',
            'peaks': peak indexes to the given 's_f',
            'dn': dn indexes to the given 's_f',
            'beats_fips': list of completed beats indexes to the given 's_f',
            'artifacts': list_artifacts indexes to the given 's_f',
            's_f': the given s_f},
      }"""
    #Dictionary labels
    artifact = 0
    foot_sys = 1
    sys_dn = 2
    dn_end = 3
    segments_dictionary = [artifact,foot_sys,sys_dn,dn_end]  
    ###################
    # Durations
    ###################
    q_signals = len(signal_list)
    # create duration array
    durations = np.zeros((q_signals),dtype=np.int)
    for i_file in np.arange(0,q_signals):
        durations[i_file] = np.shape(signal_list[i_file])[0]

    ###################
    # Resampling
    ###################
    ratio = self.f_s / s_f
    # x_rs: list containing the resampled signals
    x_rs = signal_list.copy()
    durations_rs = np.ceil(ratio*durations).astype(int)
    for i_s in np.arange(0,q_signals):
        len_signal = durations_rs[i_s]
        x_rs[i_s] = scipy.signal.resample(signal_list[i_s], num=len_signal)

    ###################
    # Form a unique dataset with chunks of signal (segments)
    ###################
    x_f = []
    qty_signals_record = []
    for i_s in np.arange(0,q_signals):
      x_i = x_rs[i_s]
      # divide signal in N° complet chunks
      x_i = [*zip(*[iter(x_i)]*self.t_window)] # dim [N° chunks, self.window]  
      qty = np.shape(x_i)[0] # N° of chunks
      qty_signals_record.append(qty)
      for i_f in np.arange(0,qty):
        x_f.append(x_i[i_f])
    q_test = np.shape(np.asarray(x_f))[0]
    x_f = np.asarray(x_f)[:,:,np.newaxis]
    ###################
    # Dataloader
    ###################
    pred_bs = 16 if q_test > 16 else q_test
    device = next(self.parameters()).device
    predict_ds = PredictDataset(x_f,device)
    # Important not to shuffle !
    predict_dl = DataLoader(predict_ds, batch_size=pred_bs, shuffle=False)
    x_input_test, predictions, probability = self.predict(predict_dl)
    detection = {}
    acum = 0 # to iterate over consecutive segment
    for i_r in np.arange(0,len(qty_signals_record)):
      #Create arrays
      pred_joined = np.asarray([])
      x_joined = np.asarray([])

      # Recover the corresponding "N" chunks with "acum" variable
      for i_s in np.arange(0,qty_signals_record[i_r]):
        x_input_test_i = x_input_test[acum] 
        pred_i = predictions[acum]
        x_joined = np.concatenate((x_joined,x_input_test_i))
        pred_joined = np.concatenate((pred_joined,pred_i))
        acum = acum + 1

      # Resampled / From model
      idx_onset,idx_peak,idx_dn,list_beats,list_artifacts = self.detection_algorithm(pred_joined,segments_dictionary)
      # Back to original f_s
      resampling_factor = 1/ratio
      # Resampling to N°chunks * len * resampling factor
      signal_o = scipy.signal.resample(x_joined,
                                        int (len(x_joined)*resampling_factor))
      
      # Interpolation for predictions acording to the recovered signal_o
      lin_model = np.linspace(0,len(x_joined)/self.f_s,len(x_joined))
      fx = interp1d(lin_model, pred_joined, kind='nearest')
      lin_o = np.linspace(0,len(signal_o)/s_f,len(signal_o))
      # Interpolated 1D
      pred_signal_o = fx(lin_o)
      # Detection based on Interpolated prediction
      idx_onset_o,idx_peak_o,idx_dn_o,list_beats_o,list_artifacts_o = self.detection_algorithm(pred_signal_o,segments_dictionary)
      # Dictionary
      detection[i_r] = {
          'original':{
            'signal': signal_o,
            'predictions': pred_signal_o,
            'onset': idx_onset_o,
            'peaks': idx_peak_o,
            'dn': idx_dn_o,
            'beats_fips': list_beats_o, # [onset,peak,dn,end],
            'artifacts': list_artifacts_o,
            's_f': s_f},
          'resampled':{
              'signal': x_joined,
              'predictions': pred_joined,
              'onset': idx_onset,
              'peaks': idx_peak,
              'dn': idx_dn,
              'beats_fips': list_beats, # [onset,peak,dn,end],
              'artifacts': list_artifacts,
              'rs_f': self.f_s}
      }
    return detection

  def detection_algorithm(self,predictions,segments_dictionary):
    """
    Inputs:
      predictions: predicted classes
      segments_dictionary: dict containing the labels of classes
    Return:
      indexis of onset, peak, dn, completed beats, fiducial points and
       regions of artifacts
    """

    artifact = segments_dictionary[0]
    foot_sys = segments_dictionary[1]
    sys_dn = segments_dictionary[2]
    dn_end = segments_dictionary[3]

    idx_onset = []
    idx_peak = []
    idx_dn = []
    list_beats = []
    #list_artifacts = []
    ####################################
    # Backward search (compelted beats)
    ####################################
    signchange = ((np.roll(predictions, 1) - predictions) != 0).astype(int)
    idx = np.where(signchange == 1)[0]
    if idx[0]==0:
        idx = np.delete(idx,0)
    idx = idx[::-1] #Backward (flip)
    len_idx = np.shape(idx)[0]

    state = 0
    for i_idx in np.arange(0,len_idx):
        current_class = predictions[idx[i_idx]]
        previous_class = predictions[idx[i_idx]-1]
        #--------------------
        # Right - End
        #--------------------
        if (((current_class == foot_sys and previous_class == dn_end) or \
            (current_class == artifact and previous_class == dn_end)) and \
          state == 0):
            state = 1 #End of Beat
            end_beat = idx[i_idx]-1
        #--------------------
        # D.Notch 
        #--------------------
        elif ((current_class == dn_end and previous_class == sys_dn) and state == 1):
            state = 2 #End of Beat
            dn = idx[i_idx]-1
            idx_dn.append(i_idx)
        #--------------------
        # D.Notch-Redundance
        #--------------------
        elif ((current_class == sys_dn and previous_class == dn_end) and state == 2):
            state = 2
        #--------------------
        #Sys.Peak
        #--------------------
        elif ((current_class == sys_dn and previous_class == foot_sys) and state == 2):
            state = 3
            peak = idx[i_idx]-1
            idx_peak.append(i_idx)
        #--------------------
        #Left - Start - Onset
        #--------------------
        #Consecutive beats
        elif ((current_class == foot_sys and previous_class == dn_end) and state == 3):
          # If the beat start with the end of another beat, it's defined end_beat's
          # next and state=1
            onset = idx[i_idx]
            beat = [onset,peak,dn,end_beat]
            list_beats.append(beat)
            idx_onset.append(i_idx)
            state = 1
            end_beat = idx[i_idx]-1
        #Artifact end
        elif ((current_class != artifact and previous_class == artifact) and state == 3):
            onset = idx[i_idx]
            beat = [onset,peak,dn,end_beat]
            list_beats.append(beat)
            idx_onset.append(i_idx)
            state = 0
    
    idx_onset = np.asarray(idx[idx_onset],dtype=int)
    idx_peak = np.asarray(idx[idx_peak],dtype=int)
    idx_dn = np.asarray(idx[idx_dn],dtype=int)
    list_beats = np.asarray(list_beats, dtype=int)
    last_beat_end = list_beats[0,-1]
    
    #if predictions[last_beat_end+1] == foot_sys:
    #  idx_onset = np.append(idx_onset,last_beat_end+1)
    
    ####################################
    # Last Unfinished Beat
    ####################################
    idx = idx[::-1] #forward
    #Only index beyond the last beat
    last_idxs = idx[idx>last_beat_end]
    #How many beyond last beat
    len_last_idx = np.shape(last_idxs)[0]
    
    last_dn = None
    for i_idxs in np.arange(0,len_last_idx):
        current_class = predictions[last_idxs[i_idxs]]
        previous_class = predictions[last_idxs[i_idxs]-1]
        #--------------------
        #Left - Start - Onset
        #--------------------
        if (current_class == foot_sys and previous_class == artifact ) or \
          (current_class == foot_sys and previous_class == dn_end ):
            state = 1
            idx_onset = np.append(idx_onset,last_idxs[i_idxs])
        #--------------------
        #Sys.Peak
        #--------------------
        if (current_class == sys_dn and previous_class == foot_sys and state==1):
        #state==1 cause it should come from the last beat detected
            state = 2
            idx_peak = np.append(idx_peak,last_idxs[i_idxs])
        #--------------------
        # D.Notch 
        #--------------------
        if (current_class == dn_end and previous_class == sys_dn and state == 2):
            last_dn = last_idxs[i_idxs]-1       
        #--------------------
        # D.Notch-Redundance
        #--------------------
        if (current_class == sys_dn and previous_class == dn_end and state == 2):
            last_dn = None
    #finally, check if last_dn was founded.    
    if last_dn != None:
        idx_dn = np.append(idx_dn,last_dn)
    
    #--------------------
    # Artifacts regions
    #--------------------
    list_artifacts = self.find_regions(0, predictions)

    #Sort
    idx_onset = np.sort(idx_onset) 
    idx_peak = np.sort(idx_peak)
    idx_dn = np.sort(idx_dn)
    
    return (idx_onset,idx_peak,idx_dn,list_beats,list_artifacts)

  def find_regions(self,value, a):
    # Create an array that is 1 where a is `value`, and pad each end with an extra 0.
    isvalue = np.concatenate(([0], np.equal(a, value).view(np.int8), [0]))
    absdiff = np.abs(np.diff(isvalue))
    # Runs start and end where absdiff is 1.
    ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
    return ranges

##############################################
# U_NET
##############################################

class DoubleConv(nn.Module):
    """(convolution => [BN] => ReLU) * 2"""
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.double_conv = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv1d(out_channels, out_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(inplace=True),
        )
    def forward(self, x):
        return self.double_conv(x)

class U_Net(nn.Module):
  def __init__(self, in_channels, out_channels, features):
    super(U_Net, self).__init__()
    self.out_channels = out_channels
    self.features = features
    self.in_channels = in_channels

    self.encoder1 = DoubleConv(in_channels,features)
    self.pool1 = nn.MaxPool1d(kernel_size=2, stride=2)

    self.encoder2 = DoubleConv(features,features*2)
    self.pool2 = nn.MaxPool1d(kernel_size=2, stride=2)

    self.encoder3 = DoubleConv(features*2,features*4)
    self.pool3 = nn.MaxPool1d(kernel_size=2, stride=2)

    self.bottleneck = DoubleConv(features*4,features*8)

    self.upconv3 =  nn.ConvTranspose1d(features*8, features*4, kernel_size=2, stride=2)
    self.decoder3 = DoubleConv((features*4)*2,features*4)

    self.upconv2 =  nn.ConvTranspose1d(features * 4, features * 2, kernel_size=2, stride=2)
    self.decoder2 = DoubleConv((features * 2)*2, features * 2)

    self.upconv1 =  nn.ConvTranspose1d(features * 2, features, kernel_size=2, stride=2)
    self.decoder1 = DoubleConv((features)*2,features)

    self.head = nn.Conv1d(features, out_channels, kernel_size=5, padding=2)

  def forward(self, x):
      enc1 = self.encoder1(x)
      enc2 = self.encoder2(self.pool1(enc1))
      enc3 = self.encoder3(self.pool2(enc2))

      bottleneck = self.bottleneck(self.pool3(enc3))

      dec3 = self.upconv3(bottleneck)
      #Si uso las conecciones tengo que duplicar
      # (*2) los input de todos los decoder
      dec3 = torch.cat((dec3, enc3), dim=1)
      dec3 = self.decoder3(dec3)
      dec2 = self.upconv2(dec3)
      dec2 = torch.cat((dec2, enc2), dim=1)
      dec2 = self.decoder2(dec2)
      dec1 = self.upconv1(dec2)
      dec1 = torch.cat((dec1, enc1), dim=1)
      dec1 = self.decoder1(dec1)
      return self.head(dec1)

##############################################
# RNN Auxiliar  (Base Class)
##############################################
class PermuteSeq(nn.Module):
    def __init__(self, permutes):
        super(PermuteSeq, self).__init__()
        self._name = 'permute'
        self.permutes = permutes
    def forward(self, inputs):
      inputs = inputs.permute(self.permutes)
      return inputs

class SelectItem(nn.Module):
    def __init__(self, item_index):
        super(SelectItem, self).__init__()
        self._name = 'selectitem'
        self.item_index = item_index
    def forward(self, inputs):
        return inputs[self.item_index]     

##############################################
# TCN (Un-Causal)
##############################################

class Chomp1d(nn.Module):
    def __init__(self, chomp_size):
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size
    def forward(self, x):
        return x[:, :, :-self.chomp_size].contiguous()

class TemporalBlock(nn.Module):
    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, padding, dropout=0.2):
        super(TemporalBlock, self).__init__()
        self.conv1 = nn.Conv1d(n_inputs, n_outputs, kernel_size,
                                           stride=stride, padding=padding, dilation=dilation)
        #self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(n_outputs, n_outputs, kernel_size,
                                           stride=stride, padding=padding, dilation=dilation)
        #self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(self.conv1, self.relu1, self.dropout1,
                                 self.conv2, self.relu2, self.dropout2)
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()
        #self.init_weights()

    def init_weights(self):
        self.conv1.weight.data.normal_(0, 0.01)
        self.conv2.weight.data.normal_(0, 0.01)
        if self.downsample is not None:
            self.downsample.weight.data.normal_(0, 0.01)

    def forward(self, x):
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)

class TemporalConvNet(nn.Module):
    def __init__(self, num_inputs, num_channels, kernel_size=3, dropout=0.2):
        super(TemporalConvNet, self).__init__()
        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 2** i
            in_channels = num_inputs if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            layers += [TemporalBlock(in_channels, out_channels, kernel_size, stride=1, dilation=dilation_size,
                                     padding=dilation_size, dropout=dropout)]

        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)

##############################################
# Deep Delineator (Full Class)
##############################################

class Deep_Delineator(Deep_Delineator_base):
  def __init__(self,args):
    super().__init__()
    self.args = args
    self.n_classes = args['n_classes']
    self.features = args['features']
    self.in_channels = args['in_channels']
    self.tcn_layers = args['tcn_layers']    
    self.tcn_drop = args['tcn_drop']
    self.device = args['device']
    self.weights = args['weights']
    self.lr = args['lr']
    self.patience_lim = args['patience_lim']
    self.name = args['name']
    self.sch_scale = args['sch_scale']
    self.t_window = args['t_window']
    self.f_s = args['f_s']
    self.regularizer = args['regularizer']
    self.epochs = 0

    # U_NET
    if args['model'] == 'U_NET':
      self.network = U_Net(self.in_channels, self.n_classes , self.features)
    
    if args['model'] == 'U_RNN':
      self.unet = U_Net(self.in_channels, self.features, self.features)
      self.rnn_layer = nn.Sequential(
          PermuteSeq((0,2,1)),
          nn.GRU(self.features, hidden_size=32, bidirectional=True, batch_first=True),
          SelectItem(0),
          nn.Linear(in_features=32*2, out_features=4),
          PermuteSeq((0,2,1)))
      self.network = nn.Sequential(self.unet,self.rnn_layer)
    # U_TCN
    if args['model'] == 'U_TCN':
      self.unet = U_Net(self.in_channels, self.features, self.features)
      # TCN
      self.tcn = TemporalConvNet(self.features, self.tcn_layers,dropout=self.tcn_drop)
      self.network = nn.Sequential(self.unet,self.tcn)
    # TCN
    if args['model'] == 'TCN':
      self.network = TemporalConvNet(self.in_channels, self.tcn_layers,dropout=self.tcn_drop)
    
    # Utils
    class_weights = torch.FloatTensor(self.weights).to(device)
    if args['loss_fn'] == 'CrossEntropy':
      self.loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    if args['optimizer'] == 'Adam':
      self.optimizer = torch.optim.Adam(self.parameters(), lr=self.lr,
                                        weight_decay=self.regularizer)
      self.scheduler = ReduceLROnPlateau(self.optimizer, 'min',
                                         patience=self.patience_lim ,
                                         factor=self.sch_scale,verbose=True)
    self.history = {'train':{'loss':[],                             
                             'acc':[]},
                    'val':{'loss':[],                           
                           'acc':[]}
                    }
    self.best_valid_loss = float('inf')     

  def forward(self, x):
      out = F.relu(self.network(x))
      return out

  def fit(self,epochs,train_dl,val_dl,path_save,save=False):

    print('-----------Start of Training------------')
    print(f'{self.name}')       

    normalizer_train = len(train_dl.dataset)
    normalizer_test = len(val_dl.dataset)

    patience = 0
    n_epochs = epochs + self.epochs
    total_epoch_loss_train = 0
    total_epoch_loss_test = 0
    accuracy_train = 0 
    accuracy_test = 0

    pbar1 = tqdm(range(self.epochs, n_epochs),unit=" epoch")
    for epoch in pbar1:
      pbar1.set_postfix({
          'P':patience,
          'Loss_t': total_epoch_loss_train,
          'Acc_t': accuracy_train,
          'Loss_v':total_epoch_loss_test,
          'Acc_v': accuracy_test,       
          'min_loss_v': self.best_valid_loss})
      total_epoch_loss_train = 0
      total_epoch_loss_test = 0
      accuracy_train = 0 
      accuracy_test = 0
      with tqdm(total=len(train_dl)+len(val_dl), unit=" batch",leave=False) as pbar2:
        # Train
        self.train()
        correct = 0
        for x, y in train_dl:
          pbar2.update(1)
          x = x.to(device)
          y = y.to(device)
          self.optimizer.zero_grad()
          out = self (x)
          #print(out.size())
          loss = self.loss_fn(out, y)
          loss.backward()
          clip_grad_norm_(self.parameters(), 5, norm_type=2.0)
          self.optimizer.step()
          _, predicted = torch.max(out.data, 1)
          total_epoch_loss_train += loss.item()
          correct_i = (predicted == y).sum().item() 
          correct += correct_i
          signal_len = x.size()[2]
          pbar2.set_postfix({
              'Loss_t:': loss.item() / x.size()[0],
              'Acc_t': correct_i / (x.size()[0] * signal_len)})
        total_epoch_loss_train = total_epoch_loss_train / normalizer_train
        accuracy_train = 100 * correct / (normalizer_train*signal_len)

        # Test
        self.eval()
        correct = 0
        with torch.no_grad():
            for i, (x, y) in enumerate(val_dl):
                pbar2.update(1)      
                x = x.to(device)
                y = y.to(device)
                out = self (x)
                test_loss = self.loss_fn(out, y)
                _, predicted = torch.max(out.data, 1)
                correct += (predicted == y).sum().item()
                total_epoch_loss_test += test_loss.item()

        signal_len = x.size()[2]
        total_epoch_loss_test = total_epoch_loss_test / normalizer_test
        accuracy_test = 100 * correct / (normalizer_test*signal_len)
        self.scheduler.step(total_epoch_loss_test)

        self.history['train']['loss'].append(total_epoch_loss_train)
        self.history['val']['loss'].append( total_epoch_loss_test)
        self.history['train']['acc'].append(accuracy_train)
        self.history['val']['acc'].append(accuracy_test)      

        if total_epoch_loss_test < self.best_valid_loss:
          self.best_valid_loss = total_epoch_loss_test
          patience = 0
          if save:
            torch.save({'epoch': epoch,
                        'model_state_dict': self.state_dict(),
                        'optimizer_state_dict': self.optimizer.state_dict(),
                        'scheduler_state_dict': self.scheduler.state_dict(),
                        'best_valid_loss': self.best_valid_loss,
                        'history': self.history,
                        'args': self.args}, '%s/%s.pt' % (path_save,self.name))          
        else:
          patience += 1        
        # EarlyStopping
        if patience > self.scheduler.patience*2 + self.scheduler.patience/2:
          return
    return

  def predict(self, dataloader):
      self.eval()
      num_elements = len(dataloader.dataset)
      num_batches = len(dataloader)
      batch_size = dataloader.batch_size
      x_input = np.zeros((num_elements,self.t_window))
      predictions = np.zeros((num_elements,self.t_window))
      probability = np.zeros((num_elements,self.n_classes,self.t_window))
      i=0;
      for x in dataloader:
          x = x.to(device)
          start = i*batch_size
          end = start + batch_size
          if i == num_batches - 1:
              end = num_elements
          out = self (x)
          proba = F.softmax(out,dim=1)
          _, pred = torch.max(out.data, 1)

          proba = proba.to(torch.device("cpu"))
          proba = proba.detach().numpy()
          x = x.to(torch.device("cpu"))
          x = x.detach().numpy()
          pred = pred.to(torch.device("cpu"))
          pred = pred.detach().numpy()
          x_input[start:end,:] = x[:,0,:]
          probability[start:end,:] = proba
          predictions[start:end,:] = pred
          i=i+1
      return (x_input,predictions,probability)

##############################################
# UTILS
##############################################

# To create and load pretrained models.
def load_checkpoint(path):
  if torch.cuda.is_available():
    map_location=lambda storage, loc: storage.cuda()
  else:
    map_location='cpu'
  assert os.path.isfile(path) , "No existe el path de los modelos guardados"  
  checkpoint = torch.load(path,map_location=map_location)
  args = checkpoint['args']
  # Model
  model = Deep_Delineator(args).to(device)
  model.load_state_dict(checkpoint['model_state_dict'])
  model.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
  model.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
  model.history = checkpoint['history']
  model.epochs = checkpoint['epoch']
  model.best_valid_loss = checkpoint['best_valid_loss']
  return model

# To load .mat files
def loadmat(filename):
    '''
    this function should be called instead of direct spio.loadmat
    as it cures the problem of not properly recovering python dictionaries
    from mat files. It calls the function check keys to cure all entries
    which are still mat-objects
    '''
    def _check_keys(d):
        '''
        checks if entries in dictionary are mat-objects. If yes
        todict is called to change them to nested dictionaries
        '''
        for key in d:
            if isinstance(d[key], sio.matlab.mio5_params.mat_struct):
                d[key] = _todict(d[key])
        return d

    def _todict(matobj):
        '''
        A recursive function which constructs from matobjects nested dictionaries
        '''
        d = {}
        for strg in matobj._fieldnames:
            elem = matobj.__dict__[strg]
            if isinstance(elem, sio.matlab.mio5_params.mat_struct):
                d[strg] = _todict(elem)
            elif isinstance(elem, np.ndarray):
                d[strg] = _tolist(elem)
            else:
                d[strg] = elem
        return d

    def _tolist(ndarray):
        '''
        A recursive function which constructs lists from cellarrays
        (which are loaded as numpy ndarrays), recursing into the elements
        if they contain matobjects.
        '''
        elem_list = []
        for sub_elem in ndarray:
            if isinstance(sub_elem, sio.matlab.mio5_params.mat_struct):
                elem_list.append(_todict(sub_elem))
            elif isinstance(sub_elem, np.ndarray):
                elem_list.append(_tolist(sub_elem))
            else:
                elem_list.append(sub_elem)
        return elem_list
    data = sio.loadmat(filename, struct_as_record=False, squeeze_me=True)
    return _check_keys(data)

