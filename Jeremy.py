import numpy as np
import datetime, os
import sys
from keras.models import Sequential, Model
from keras.layers import Dense, Dropout, Conv1D, MaxPooling1D, Flatten, Input, Concatenate
import tensorflow as tf
import numpy as np
import keras
import matplotlib
import sklearn
from sklearn.metrics import confusion_matrix, roc_auc_score
import astropy as ap
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from exop import main as exopmain

# ----------------------------------------------------------------------------------

# DATACLASS

class gdatstrt(object):
    
    """
    init: Initializes all the testing data -- has all variables needed for testing
    appdfcon: add a fully connected layer
    appdcon1: add a 1D convolutional layer
    retr_metr: returns all metrics of the network
    """
    
    def __init__(self):
    
        # fraction of data samples that will be used to test the model
        self.fractest = 0.1
    
        # number of epochs
        self.numbepoc = 3
    
        # number of runs for each configuration in order to determine the statistical uncertainty
        self.numbruns = 1

        self.indxepoc = np.arange(self.numbepoc)
        self.indxruns = np.arange(self.numbruns)

        # a dictionary to hold the variable values for which the training will be repeated
        self.listvalu = {}
        ## generative parameters of mock data
        self.listvalu['zoomtype'] = ['locl', 'glob']

        self.listvalu['numbtime'] = np.array([1e1, 3e1, 1e2, 3e2, 1e3]).astype(int)
        # temp
        self.listvalu['dept'] = 1 - np.array([(i+2)*10**(-1) for i in range(5)]) # 1e-3, 3e-3, 1e-2, 3e-2, 1e-1]) 

        self.listvalu['nois'] = np.array([0.03*(i+1)  for i in range(5)]) # SNR 10**(-2)*(i)

        self.listvalu['numbdata'] = np.array([3e3, 1e4 , 3e3, 1e5, 3e5]).astype(int)

        self.listvalu['fracplan'] = [0.1, 0.3 , 0.5, 0.7, 0.9] # frac P/N IDEAL BETWEEN .5-.7

        ## hyperparameters
        self.listvalu['numbdatabtch'] = [5, 10, 16, 20, 25] # IDEAL 16~25
        ### number of layers
        self.listvalu['numblayr'] = [1, 2, 2, 4, 5] # IDEAL 2 (FOR GLOBAL)
        ### number of dimensions in each layer
        self.listvalu['numbdimslayr'] = [240, 250, 260, 270, 280] # IDEAL IS ~256 || 280 (sacrifices speed a lot)
        ### fraction of dropout in in each layer
        self.listvalu['fracdrop'] = [0.38, 0.39, 0.42, 0.41, 0.42] # IDEAL is ~0.42
        
        # list of strings holding the names of the variables
        self.liststrgvarb = self.listvalu.keys()
        
        self.numbvarb = len(self.liststrgvarb) # number of variables
        self.indxvarb = np.arange(self.numbvarb) # array of all indexes to get any variable
        
        self.numbvalu = np.empty(self.numbvarb, dtype=int)
        self.indxvalu = [[] for o in self.indxvarb]
        for o, strgvarb in enumerate(self.liststrgvarb):
            self.numbvalu[o] = len(self.listvalu[strgvarb])
            self.indxvalu[o] = np.arange(self.numbvalu[o])
    

        # dictionary to hold the metrics resulting from the runs
        self.dictmetr = {}
        self.liststrgmetr = ['prec', 'accu', 'reca']
        self.listlablmetr = ['Precision', 'Accuracy', 'Recall']
        self.liststrgrtyp = ['vali', 'tran']
        self.listlablrtyp = ['Training', 'Validation']
        self.numbrtyp = len(self.liststrgrtyp)
        self.indxrtyp = np.arange(self.numbrtyp)
        
        for o, strgvarb in enumerate(self.liststrgvarb):
            self.dictmetr[strgvarb] = np.empty((2, 3, self.numbruns, self.numbvalu[o]))

# -----------------------------------------------------------------------------------

# MODELS

# models from "Scientific Domain Knowledge Improves Exoplanet Transit Classification with Deep Learning"

paperloclinpt = 201      # input shape from paper [local val]
papergloblinpt = 2001    # input shape from paper

def exonet():
    loclinpt, globlinpt = 201, 2001 # hard coded for now
    localinput = Input(shape=(int(loclinpt),), dtype='float32', name='localinput') 

    x = Conv1D(5, 16, activation='relu', input_shape=(None,loclinpt))(localinput)
    x = Conv1D(5, 16, activation='relu')(x)

    x = MaxPooling1D(pool_size=7, strides=2)(x)

    x = Conv1D(5, 32, activation='relu')(x)
    x = Conv1D(5, 32, activation='relu')(x)

    x = MaxPooling1D(pool_size=7, strides=2)(x)

    # -----------------------------------------------------------------------------
    globalinput = Input(shape=(int(globlinpt),), dtype='float32', name='globalinput')

    y = Conv1D(5, 16, activation='relu', input_shape=(None,loclinpt))(globalinput)
    y = Conv1D(5, 16, activation='relu')(y)

    y = MaxPooling1D(pool_size=5, strides=2)(y)

    y = Conv1D(5, 32, activation='relu')(y)
    y = Conv1D(5, 32, activation='relu')(y)

    y = MaxPooling1D(pool_size=5, strides=2)(y)

    y = Conv1D(5, 64, activation='relu')(y)
    y = Conv1D(5, 64, activation='relu')(y)

    y = MaxPooling1D(pool_size=5, strides=2)(y)

    y = Conv1D(5, 128, activation='relu')(y)
    y = Conv1D(5, 128, activation='relu')(y)

    y = MaxPooling1D(pool_size=5, strides=2)(y)

    y = Conv1D(5, 256, activation='relu')(y)
    y = Conv1D(5, 256, activation='relu')(y)

    y = MaxPooling1D(pool_size=5, strides=2)(y)

    # ------------------------------------------------------------------------------
    z = keras.layers.concatenate([x, y])

    # ------------------------------------------------------------------------------

    z = Dense(512, activation='relu')(z)
    z = Dense(512, activation='relu')(z)
    z = Dense(512, activation='relu')(z)
    z = Dense(512, activation='relu')(z)

    # ------------------------------------------------------------------------------
    finllayr = Dense(1, activation='sigmoid', name='finl')(z)

    # ------------------------------------------------------------------------------
    modlfinl = Model(inputs=[localinput, globalinput], outputs=[finllayr])

    modlfinl.compile(loss='binary_crossentropy', optimizer='sgd', metrics=['accuracy'])

    return modlfinl

def reduced():
    loclinpt, globlinpt = 201, 2001 # hard coded for now
    localinput = Input(shape=(int(loclinpt),), dtype='float32', name='localinput') 

    x = Conv1D(5, 16, activation='relu', input_shape=(None,loclinpt))(localinput)

    x = MaxPooling1D(pool_size=2, strides=2)(x)

    x = Conv1D(5, 16, activation='relu')(x)


    # x = MaxPooling1D()(x)

    # -----------------------------------------------------------------------------
    globalinput = Input(shape=(int(globlinpt),), dtype='float32', name='globalinput')

    y = Conv1D(5, 16, activation='relu', input_shape=(None,loclinpt))(globalinput)

    y = MaxPooling1D(pool_size=2, strides=2)(y)

    y = Conv1D(5, 16, activation='relu')(y)

    y = MaxPooling1D(pool_size=2, strides=2)(y)

    y = Conv1D(5, 32, activation='relu')(y)

    # y = MaxPooling1D()(y)

    # ------------------------------------------------------------------------------
    z = keras.layers.concatenate([x, y])

    z = MaxPooling1D()(z)
    # ------------------------------------------------------------------------------

    z = Dense(1, activation='relu')(z)

    # ------------------------------------------------------------------------------
    finllayr = Dense(1, activation='sigmoid', name='finl')(z)

    # ------------------------------------------------------------------------------
    modlfinl = Model(inputs=[localinput, globalinput], outputs=[finllayr])

    modlfinl.compile(loss='binary_crossentropy', optimizer='sgd', metrics=['accuracy'])

    return modlfinl


# self-generative models 

# can be called in 'vary___' functions
def singleinput(dataclass,fracdropbool=True):
    """
    CURRENTLY ONLY DENSE LAYERS, COULD BE MORE MODULAR
    dataclass : instance of gdat

    layers : number of layers 

    fracdropbool : true or false on doing the fracdrop
    """

    numbtime = dataclass.numbtime
    numbdimslayr = dataclass.numbdimslayr
    fracdrop = dataclass.fracdrop
    layers = dataclass.numblayr
    inptshape = dataclass.inpt.shape
    unused, useddim = inptshape
    

    input_S = Input(shape=(useddim,), dtype='float32', name='input')

    x = Dense(numbdimslayr, input_dim=numbtime, activation='relu')(input_S)
    
    if fracdropbool:
        x = Dropout(fracdrop)(x)

    for i in range(layers-1):
        x = Dense(numbdimslayr, activation='relu')(x)
        
        if fracdropbool:
            x = Dropout(fracdrop)(x)

    finllayr = Dense(1, activation='sigmoid', name='finl')(x)
    
    modlfinl = Model(inputs=[input_S], outputs=[finllayr])

    modlfinl.compile(loss='binary_crossentropy', optimizer='sgd', metrics=['accuracy'])

    return modlfinl

# can't be called in 'vary___' functions yet
def twoinput(dataclass, layers, fracdropbool=True):
    """
    CURRENTLY ONLY DENSE LAYERS, COULD BE MORE MODULAR
    dataclass is an instance of gdat

    layers is a list of layer quantities:
        [0] := number of local
        [1] := number of global
        [2] := number after being combined 
    """
    numbtime = dataclass.numbtime
    numbdimslayr = dataclass.numbdimslayr
    fracdrop = dataclass.fracdrop
    
    # ----------------------------------------------------------------------------
    localinput = Input(shape=(int(numbtime),), dtype='float32', name='localinput')

    x = Dense(numbdimslayr, input_dim=numbtime, activation='relu')(localinput)
    
    if fracdropbool:
        x = Dropout(fracdrop)(x)

    for i in range(layers[0]-1):
        x = Dense(numbdimslayr, activation='relu')(x)
        
        if fracdropbool:
            x = Dropout(fracdrop)(x)


    # -----------------------------------------------------------------------------
    globalinput = Input(shape=(int(numbtime),), dtype='float32', name='globalinput')

    y = Dense(numbdimslayr, input_dim=numbtime, activation='relu')(globalinput)
    
    if fracdropbool:
        y = Dropout(fracdrop)(y)

    for i in range(layers[1]-1):
        y = Dense(numbdimslayr, activation='relu')(y)
        
        if fracdropbool:
            y = Dropout(fracdrop)(y)

    # ------------------------------------------------------------------------------
    z = keras.layers.concatenate([x, y])

    # ------------------------------------------------------------------------------
    if layers[2] >=2:
        z = Dense(numbdimslayr, activation='relu')(z)
        
        for i in range(layers[2]-2):
            z = Dense(numbdimslayr, activation='relu')(z)

    # ------------------------------------------------------------------------------
    finllayr = Dense(1, activation='sigmoid', name='finl')(z)

    # ------------------------------------------------------------------------------
    modlfinl = Model(inputs=[localinput, globalinput], outputs=[finllayr])

    modlfinl.compile(loss='binary_crossentropy', optimizer='sgd', metrics=['accuracy'])

    return modlfinl

# ------------------------------------------------------------------------------------

# GET-METRICS-THRU-VARIABLES

def summgene(varb):
    '''
    convenience function to quickly print a numpy array
    '''
    
    print (np.amin(varb))
    print (np.amax(varb))
    print (np.mean(varb))
    print (varb.shape)

def vary_all(dataclass, modelfunc, datatype='here'):
    
    '''
    Function to explore the effect of hyper-parameters (and data properties for mock data) on binary classification metrics
    '''
    
    # global object that will hold global variables
    # this can be wrapped in a function to allow for customization 
    # initialize the data here
    gdat = dataclass

    ## time stamp string
    strgtimestmp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # print ('CtC explorer initialized at %s.' % strgtimestmp)
    
    ## path where plots will be generated
    pathplot = os.environ['TDGU_DATA_PATH'] + '/'
    
    # temp
    gdat.maxmindxvarb = 10

    # for each run
    for t in gdat.indxruns:
        
        # for each variable
        for o, strgvarb in enumerate(gdat.liststrgvarb): 
            
            if o == gdat.maxmindxvarb:
                break

            pr_points = []

            # for each value
            for i in gdat.indxvalu[o]:

                for strgvarbtemp in gdat.liststrgvarb: 
                    setattr(gdat, strgvarbtemp, gdat.listvalu[strgvarbtemp][int(gdat.numbvalu[o]/2)])
                setattr(gdat, strgvarb, gdat.listvalu[strgvarb][i])
                
                # for strgvarbtemp in gdat.liststrgvarb: 
                #print (strgvarb, getattr(gdat, strgvarb))

                gdat.numbplan = int(gdat.numbdata * gdat.fracplan)
                gdat.numbnois = gdat.numbdata - gdat.numbplan
                
                gdat.indxtime = np.arange(gdat.numbtime)
                gdat.indxdata = np.arange(gdat.numbdata)
                gdat.indxlayr = np.arange(gdat.numblayr)

                # number of test data samples
                gdat.numbdatatest = int(gdat.numbdata * gdat.fractest)
                # number of training data samples
                gdat.numbdatatran = gdat.numbdata - gdat.numbdatatest
                # number of signal data samples
                numbdataplan = int(gdat.numbdata * gdat.fracplan)
                
                if datatype == 'here':
                    gdat.inpt, gdat.outp = exopmain.retr_datamock(numbplan=gdat.numbplan, numbnois=gdat.numbnois, numbtime=gdat.numbtime, dept=gdat.dept, nois=gdat.nois)

                if datatype == 'ete6':
                    gdat.inpt, gdat.outp = exopmain.retr_ete6()                    


                # divide the data set into training and test data sets
                numbdatatest = int(gdat.fractest * gdat.numbdata)
                gdat.inpttest = gdat.inpt[:numbdatatest, :]
                gdat.outptest = gdat.outp[:numbdatatest]
                gdat.inpttran = gdat.inpt[numbdatatest:, :]
                gdat.outptran = gdat.outp[numbdatatest:]   
                
                gdat.modl = modelfunc(gdat, )
                # gdat.modl.summary()
                prec, recal = thresh(gdat, points=200)


                y_pred = gdat.modl.predict(gdat.inpttest)
                y_real = gdat.outptest
                auc = roc_auc_score(y_real, y_pred)

                
                """
                INCLUDE:
                1) SIGNAL TO NOISE checkplus
                2) GAUSSIAN STANDARD DEVIATION
                3) DEPTH 
                4) AUC checkplus
                """
                textstr = '\n'.join((
                    r'$\mathrm{Signal:Noise}=%.2f$' % (gdat.dept/gdat.nois, ),
                    # r'$\mathrm{Gaussian Standard Deviation}=%.2f$' % (auc, ),
                    r'$\mathrm{AUC}=%.8f$' % (auc, ),
                    r'$\mathrm{Depth}=%.2f$' % (gdat.dept, )))
            

                figr, axis = plt.subplots()
                axis.plot(prec, recal, marker='o', ls='', markersize=3, alpha=0.6)
                axis.axhline(1, alpha=.5)
                axis.axvline(1, alpha=.5)
                props = dict(boxstyle='round', alpha=0.5)
                axis.text(0.05, 0.25, textstr, transform=axis.transAxes, fontsize=14, verticalalignment='top', bbox=props)
                plt.tight_layout()
                plt.xlabel('Recall')
                plt.ylabel('Precision')
                plt.title('Precision v Recall, {0}{1}, {2}'.format(str(strgvarbChng), str(getattr(gdat, strgvarbChng)), zoomType))
                # plt.legend()
                path = pathplot + '{0}PvR_{1}_{2}{3}_'.format(t, zoomType, strgvarbChng, getattr(gdat, strgvarbChng)) + strgtimestmp + '.pdf' 
                plt.savefig(path)
                plt.close()
                    

    return strgtimestmp

# this one works fine
def vary_one(dataclass, strgvarbChng, modelfunc, datatype='here', zoomType='local'):
    gdat = dataclass

    ## time stamp string
    strgtimestmp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    ## path where plots will be generated
    pathplot = os.environ['TDGU_DATA_PATH'] + '/'

    # for each value
    for i in range(len(gdat.listvalu[strgvarbChng])):

        for strgvarbtemp in gdat.liststrgvarb:
            if strgvarbtemp != strgvarbChng:
                o = len(gdat.listvalu[strgvarbtemp]) 
                setattr(gdat, strgvarbtemp, gdat.listvalu[strgvarbtemp][int(gdat.numbvalu[o]/2)])
        setattr(gdat, strgvarbChng, gdat.listvalu[strgvarbChng][i])
        
        # print(gdat.listvalu[strgvarbChng][i])

        
        gdat.numbplan = int(gdat.numbdata * gdat.fracplan)
        gdat.numbnois = gdat.numbdata - gdat.numbplan
        
        gdat.indxtime = np.arange(gdat.numbtime)
        gdat.indxdata = np.arange(gdat.numbdata)
        gdat.indxlayr = np.arange(gdat.numblayr)

        # number of test data samples
        gdat.numbdatatest = int(gdat.numbdata * gdat.fractest)
        # number of training data samples
        gdat.numbdatatran = gdat.numbdata - gdat.numbdatatest
        # number of signal data samples
        numbdataplan = int(gdat.numbdata * gdat.fracplan)
        
        if datatype == 'here':
            gdat.inpt, gdat.outp = exopmain.retr_datamock(numbplan=gdat.numbplan, numbnois=gdat.numbnois, numbtime=gdat.numbtime, dept=gdat.dept, nois=gdat.nois)

        if datatype == 'ete6':
            gdat.inpt, gdat.outp = exopmain.retr_ete6()                    

        # divide the data set into training and test data sets
        numbdatatest = int(gdat.fractest * gdat.numbdata)
        gdat.inpttest = gdat.inpt[:numbdatatest, :]
        gdat.outptest = gdat.outp[:numbdatatest]
        gdat.inpttran = gdat.inpt[numbdatatest:, :]
        gdat.outptran = gdat.outp[numbdatatest:]   

        """
        # optional graphing of input light curves
        figr, axis = plt.subplots() # figr unused
        for k in gdat.indxdata:
            if k < 10:
                if gdat.outp[k] == 1:
                    colr = 'r'
                else:
                    colr = 'b'
                axis.plot(gdat.indxtime, gdat.inpt[k, :], marker='o', ls='-', markersize=5, alpha=0.6, color=colr)
        plt.tight_layout()
        plt.xlabel('time')
        plt.ylabel('data-input')
        plt.title('input vs time')
        plt.legend()
        path = pathplot + 'inpt_%s%s%04d' % (zoomType, strgvarbChng, i) + strgtimestmp + '.pdf' 
        plt.savefig(path)
        plt.close()
        """


        for t in range(len(gdat.indxruns)):
 
            gdat.modl = modelfunc(gdat, )
            # gdat.modl.summary()
            prec, recal = thresh(gdat, points=200)


            y_pred = gdat.modl.predict(gdat.inpttest)
            y_real = gdat.outptest
            auc = roc_auc_score(y_real, y_pred)

            
            """
            INCLUDE:
            1) SIGNAL TO NOISE checkplus
            2) GAUSSIAN STANDARD DEVIATION
            3) DEPTH 
            4) AUC checkplus
            """
            textstr = '\n'.join((
                r'$\mathrm{Signal:Noise}=%.2f$' % (gdat.dept/gdat.nois, ),
                # r'$\mathrm{Gaussian Standard Deviation}=%.2f$' % (auc, ),
                r'$\mathrm{AUC}=%.8f$' % (auc, ),
                r'$\mathrm{Depth}=%.2f$' % (gdat.dept, )))
        

            figr, axis = plt.subplots()
            axis.plot(prec, recal, marker='o', ls='', markersize=3, alpha=0.6)
            axis.axhline(1, alpha=.5)
            axis.axvline(1, alpha=.5)
            props = dict(boxstyle='round', alpha=0.5)
            axis.text(0.05, 0.25, textstr, transform=axis.transAxes, fontsize=14, verticalalignment='top', bbox=props)
            plt.tight_layout()
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.title('Precision v Recall, {0}{1}, {2}'.format(str(strgvarbChng), str(getattr(gdat, strgvarbChng)), zoomType))
            # plt.legend()
            path = pathplot + '{0}PvR_{1}_{2}{3}_'.format(t, zoomType, strgvarbChng, getattr(gdat, strgvarbChng)) + strgtimestmp + '.pdf' 
            plt.savefig(path)
            plt.close()

# this varies over threshold values
def thresh(dataclass, points=100, indxvaluthis=None, strgvarbthis=None):
    
    pointsX = []
    pointsY = []
    thresholds = [0.3 + i/(points*2) for i in range(points)]
    modelinst = dataclass.modl
    
    for y in dataclass.indxepoc:
        
        modelinst.fit(dataclass.inpt, dataclass.outp, epochs=dataclass.numbepoc, batch_size=dataclass.numbdatabtch, validation_split=dataclass.fractest, verbose=1)
        
        for r in dataclass.indxrtyp:
            if r==0:
                inpt = dataclass.inpttran
                outp = dataclass.outptran
            else:
                inpt = dataclass.inpttest
                outp = dataclass.outptest

            inpt = inpt[:, :]

             
            for i in thresholds:
                

                outppred = (modelinst.predict(inpt) > i).astype(int)
                matrconf = confusion_matrix(outp, outppred)

                if matrconf.size == 1:
                    matrconftemp = np.copy(matrconf)
                    matrconf = np.empty((2, 2))
                    matrconf[0, 0] = matrconftemp

                trne = matrconf[0, 0]
                flpo = matrconf[0, 1]
                flne = matrconf[1, 0]
                trpo = matrconf[1, 1]

                

                if float(trpo + flpo) > 0:
                    Precision = trpo / float(trpo + flpo) # precision
                else:
                    Precision = 0
                    # print ('No positive found...')
                    # raise Exception('')
                # metr[y, r, 1] = float(trpo + trne) / (trpo + flpo + trne + flne) # accuracy
                if float(trpo + flne) > 0:
                    Recall = trpo / float(trpo + flne) # recall
                else:
                    Recall = 0
                    # raise Exception('')

                if Precision == 0 and Recall == 0:
                    pass
                    
                else:
                    pointsX.append(Precision)
                    pointsY.append(Recall)
    return pointsX, pointsY


# binning
def binn_lcur(numbtime, time, flux, peri, epoc, zoomtype='glob'):
    
    timefold = ((time - epoc) / peri + 0.25) % 1.
    
    if zoomtype == 'glob':
        minmtimefold = 0.
        maxmtimefold = 1.
    else:
        minmtimefold = 0.15
        maxmtimefold = 0.35
    binstimefold = np.linspace(minmtimefold, maxmtimefold, numbtime + 1)
    indxtime = np.arange(numbtime)
    fluxavgd = np.empty(numbtime)
    for k in indxtime:
        indx = np.where((binstimefold[k] < timefold) & (timefold < binstimefold[k+1]))[0]
        fluxavgd[k] = np.mean(flux[indx])

    return fluxavgd


# to vary on paper models
def vary_one_paper( dataclass, \
                    strgvarbChng, \
                    modelfunc, \
                    datatype='here', \
                    zoomType='local', \
                    saveinpt=False, \
                    phastype='fold'):
    
    gdat = dataclass

    gdat.phastype = phastype
    
    ## time stamp string
    strgtimestmp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    ## path where plots will be generated
    pathplot = os.environ['TDGU_DATA_PATH'] + '/'
    

    # NEW
    os.system('mkdir -p %s' % pathplot)

    gdat.numbtimebins = 100
    gdat.indxtimebins = np.arange(gdat.numbtimebins)

    # temp
    gdat.maxmindxvarb = 10
    # END NEW


    # for each value
    for i in range(len(gdat.listvalu[strgvarbChng])):

        for strgvarbtemp in gdat.liststrgvarb:
            if strgvarbtemp != strgvarbChng:
                # set all but the varying variable to their mid-value
                o = len(gdat.listvalu[strgvarbtemp]) 
                setattr(gdat, strgvarbtemp, gdat.listvalu[strgvarbtemp][int(gdat.numbvalu[o]/2)])

        setattr(gdat, strgvarbChng, gdat.listvalu[strgvarbChng][i])

        
        gdat.numbplan = int(gdat.numbdata * gdat.fracplan)
        gdat.numbnois = gdat.numbdata - gdat.numbplan
        
        gdat.indxtime = np.arange(gdat.numbtime)
        gdat.indxdata = np.arange(gdat.numbdata)
        gdat.indxlayr = np.arange(gdat.numblayr)

        # number of test data samples
        gdat.numbdatatest = int(gdat.numbdata * gdat.fractest)
        # number of training data samples
        gdat.numbdatatran = gdat.numbdata - gdat.numbdatatest
        # number of signal data samples
        numbdataplan = int(gdat.numbdata * gdat.fracplan)
        
        if datatype == 'here':
            gdat.inptraww, gdat.outp = exopmain.retr_datamock(numbplan=gdat.numbplan, \
                numbnois=gdat.numbnois, numbtime=gdat.numbtime, dept=gdat.dept, nois=gdat.nois)

        if datatype == 'ete6':
            print ('gdat.numbdata',gdat.numbdata)
            gdat.time, gdat.inptraww, gdat.outp, gdat.tici, gdat.peri = exopmain.retr_ete6(gdat.phastype, \
                                                                        numbdata=gdat.numbdata, nois=gdat.nois)
                    
            if gdat.phastype == 'raww':
                gdat.inpt = gdat.inptraww

            elif gdat.phastype == 'fold':
                pathsavefold= pathplot + 'savefold_%s%s%04d' % (datatype, gdat.zoomtype, gdat.numbtimebins) + '.dat' 
                if not os.path.exists(pathsavefold):
                    cntr = 0
                    gdat.inptfold = np.empty((gdat.numbdata, gdat.numbtimebins))
                    for k in gdat.indxdata:
                        numbperi = gdat.peri[cntr].size
                        indxperi = np.arange(numbperi)
                        """
                        # temp -- only uses the first period
                        print 'k'
                        print k
                        print 'gdat.inptfold'
                        summgene(gdat.inptfold)
                        print 'gdat.inptraww'
                        summgene(gdat.inptraww)
                        print 'gdat.peri[k]'
                        print gdat.peri[k]
                        print
                        """
                        gdat.inptfold[k, :] = binn_lcur(gdat.numbtimebins, gdat.time, gdat.inptraww[k, :], abs(gdat.peri[k][0]), 0., \
                                                                                                                            zoomtype=gdat.zoomtype)
                
                    print ('Writing to %s...') % pathsavefold
                    np.savetxt(pathsavefold, gdat.inptfold)
                else:
                    print ('Reading from %s...') % pathsavefold
                    gdat.inptfold = np.loadtxt(pathsavefold)
                gdat.inpt = gdat.inptfold

            elif gdat.phastype == 'both':
                gdat.inptR = gdat.inptraww

                pathsavefold= pathplot + 'savefold_%s%s%04d' % (datatype, gdat.zoomtype, gdat.numbtimebins) + '.dat' 
                if not os.path.exists(pathsavefold):
                    cntr = 0
                    gdat.inptfold = np.empty((gdat.numbdata, gdat.numbtimebins))
                    for k in gdat.indxdata:
                        numbperi = gdat.peri[cntr].size
                        indxperi = np.arange(numbperi)
                        """
                        # temp -- only uses the first period
                        print 'k'
                        print k
                        print 'gdat.inptfold'
                        summgene(gdat.inptfold)
                        print 'gdat.inptraww'
                        summgene(gdat.inptraww)
                        print 'gdat.peri[k]'
                        print gdat.peri[k]
                        print
                        """
                        gdat.inptfold[k, :] = binn_lcur(gdat.numbtimebins, gdat.time, gdat.inptraww[k, :], abs(gdat.peri[k][0]), 0., \
                                                                                                                            zoomtype=gdat.zoomtype)
                
                    print ('Writing to %s...') % pathsavefold
                    np.savetxt(pathsavefold, gdat.inptfold)
                else:
                    print ('Reading from %s...') % pathsavefold
                    gdat.inptfold = np.loadtxt(pathsavefold)
                gdat.inptF = gdat.inptfold

        # divide the data set into training and test data sets
        if gdat.phastype == 'raww' or gdat.phastype == 'fold':

            numbdatatest = int(gdat.fractest * gdat.numbdata)
            gdat.inpttest = gdat.inpt[:numbdatatest, :]
            gdat.outptest = gdat.outp[:numbdatatest]
            gdat.inpttran = gdat.inpt[numbdatatest:, :]
            gdat.outptran = gdat.outp[numbdatatest:] 

        elif gdat.phastype == 'both':

            numbdatatest = int(gdat.fractest * gdat.numbdata)

            gdat.inpttestR = gdat.inptR[:numbdatatest, :] # R for raw --> global
            gdat.inpttranR = gdat.inptR[numbdatatest:, :]

            gdat.inpttestF = gdat.inptF[:numbdatatest, :] # F for folded --> local
            gdat.inpttranF = gdat.inptF[numbdatatest:, :]

            gdat.outptest = gdat.outp[:numbdatatest]
            gdat.outptran = gdat.outp[numbdatatest:] 


        
        # optional graphing of input light curves
        if saveinpt:
            figr, axis = plt.subplots() # figr unused
            for k in gdat.indxdata:
                if k < 10:
                    if gdat.outp[k] == 1:
                        colr = 'r'
                    else:
                        colr = 'b'
                    
                    if gdat.phastype == 'raww':
                        indx = gdat.indxtime
                        axis.plot(indx, gdat.inpt[k, :], marker='o', ls='-', markersize=5, alpha=0.6, color=colr)
                    if gdat.phastype == 'fold':
                        indx = gdat.indxtimebins
                        axis.plot(indx, gdat.inpt[k, :], marker='o', ls='-', markersize=5, alpha=0.6, color=colr)
                    
                    if gdat.phastype == 'both':
                        indxR = gdat.indxtime # for Raww part
                        indxF = gdat.indxtimebins # for folded part

                        inv = 'g'
                        axis.plot(indxR, gdat.inptR[k, :], str(colr+ 'o'), indxF, gdat.inptF[k, :], str(inv+ 'o'), ls='-', markersize=5, alpha=0.6, )
                    
                    
            plt.tight_layout()
            plt.xlabel('time')
            plt.ylabel('data-input')
            plt.title('input vs time')
            plt.legend()
            path = pathplot + 'inpt_%s%s%04d' % (zoomType, strgvarbChng, i) + strgtimestmp + '.pdf' 
            plt.savefig(path)
            plt.close()
        


        for t in range(len(gdat.indxruns)):
 
            gdat.modl = modelfunc()

            # gdat.modl.summary()

            prec, recal = thresh_paper(gdat, points=200)

            if gdat.phastype == 'both':
                y_pred = gdat.modl.predict([gdat.inpttestF, gdat.inpttestR])

            else:
                y_pred = gdat.modl.predict(gdat.inpttest)

            y_real = gdat.outptest
            auc = roc_auc_score(y_real, y_pred)


            textstr = '\n'.join((
                r'$\mathrm{Signal:Noise}=%.2f$' % (gdat.dept/gdat.nois, ),
                # r'$\mathrm{Gaussian Standard Deviation}=%.2f$' % (auc, ),
                r'$\mathrm{AUC}=%.8f$' % (auc, ),
                r'$\mathrm{Depth}=%.2f$' % (gdat.dept, )))
        

            figr, axis = plt.subplots()
            axis.plot(prec, recal, marker='o', ls='', markersize=3, alpha=0.6)
            axis.axhline(1, alpha=.5)
            axis.axvline(1, alpha=.5)
            props = dict(boxstyle='round', alpha=0.5)
            axis.text(0.05, 0.25, textstr, transform=axis.transAxes, fontsize=14, verticalalignment='top', bbox=props)
            plt.tight_layout()
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.title('Precision v Recall, {0}{1}, {2}'.format(str(strgvarbChng), str(getattr(gdat, strgvarbChng)), zoomType))
            # plt.legend()
            path = pathplot + '{0}PvR_{1}_{2}{3}_'.format(t, zoomType, strgvarbChng, getattr(gdat, strgvarbChng)) + strgtimestmp + '.pdf' 
            plt.savefig(path)
            plt.close()

# to vary thresholds on a multi-input model
def thresh_paper(dataclass, points=100, indxvaluthis=None, strgvarbthis=None):
    
    pointsX = []
    pointsY = []
    thresholds = [0.3 + i/(points*2) for i in range(points)]
    modelinst = dataclass.modl
    
    for y in dataclass.indxepoc:
        
        if dataclass.phastype == 'both':
            modelinst.fit([dataclass.inptF, dataclass.inptR], dataclass.outp, epochs=dataclass.numbepoc, batch_size=dataclass.numbdatabtch, validation_split=dataclass.fractest, verbose=1)
        else: 
            modelinst.fit(dataclass.inpt, dataclass.outp, epochs=dataclass.numbepoc, batch_size=dataclass.numbdatabtch, validation_split=dataclass.fractest, verbose=1)
        
        for r in dataclass.indxrtyp:
            if dataclass.phastype == 'both':
                if r==0:
                    inptF = dataclass.inpttranF
                    inptR = dataclass.inpttranR
                    outp = dataclass.outptran

                else:
                    inptF = dataclass.inpttestF
                    inptR = dataclass.inpttestR
                    outp = dataclass.outptest

                inptF = inptF[:, :]
                inptR = inptR[:, :]

            else:
                if r==0:
                    inpt = dataclass.inpttran
                    outp = dataclass.outptran

                else:
                    inpt = dataclass.inpttest
                    outp = dataclass.outptest

                inpt = inpt[:, :]
             
            for i in thresholds:
                
                if dataclass.phastype == 'both':
                    outppred = (modelinst.predict([inptF, inptR]) > i).astype(int)

                else:
                    outppred = (modelinst.predict(inpt) > i).astype(int)
                
                matrconf = confusion_matrix(outp, outppred)

                if matrconf.size == 1:
                    matrconftemp = np.copy(matrconf)
                    matrconf = np.empty((2, 2))
                    matrconf[0, 0] = matrconftemp

                trne = matrconf[0, 0]
                flpo = matrconf[0, 1]
                flne = matrconf[1, 0]
                trpo = matrconf[1, 1]

                

                if float(trpo + flpo) > 0:
                    Precision = trpo / float(trpo + flpo) # precision
                else:
                    Precision = 0
                    # print ('No positive found...')
                    # raise Exception('')
                # metr[y, r, 1] = float(trpo + trne) / (trpo + flpo + trne + flne) # accuracy
                if float(trpo + flne) > 0:
                    Recall = trpo / float(trpo + flne) # recall
                else:
                    Recall = 0
                    # raise Exception('')

                if Precision == 0 and Recall == 0:
                    pass
                    
                else:
                    pointsX.append(Precision)
                    pointsY.append(Recall)
    return pointsX, pointsY


