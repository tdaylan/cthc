import datetime, os, sys, argparse, random, pathlib, time

from tqdm import tqdm, trange
import numpy as np

from keras.models import Model, load_model
from keras.callbacks import ModelCheckpoint, TensorBoard

import sklearn
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

import astropy as ap
import astropy.io.fits as fits

from scipy.interpolate import LSQUnivariateSpline

import matplotlib
import matplotlib.pyplot as plt

import seaborn as sns

import lightkurve

from exop.main import retr_datamock, retr_datatess 

from models import exonet, reduced

import pickle
import re

# -----------------------------------------------------------------------------------


# TO ALLOW EASY ACCESS TO SUBFOLDERS
class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


# -----------------------------------------------------------------------------------


# TRAINING
fractest = 0.3

numbepoc = 50
indxepoc = np.arange(numbepoc)

datatype = 'tess'

modl = reduced

overwrite = True

l1_param = 0.1
l2_param = 0.1

loclsize = 200
globsize = 2000
# -----------------------------------------------------------------------------------

# FOR PRECISION AND RECALL

# points for thresholds graphing
points_thresh = 100
thresh = np.linspace(0.2, 0.9, points_thresh)


# -----------------------------------------------------------------------------------


# hyperparams will go here for model optimization



# -----------------------------------------------------------------------------------

from bisect import bisect_left

def takeClosest(myList, myNumber):
    """
    Assumes myList is sorted. Returns closest value to myNumber.

    If two numbers are equally close, return the smallest number.
    """
    pos = bisect_left(myList, myNumber)
    if pos == 0:
        return myList[0]
    if pos == len(myList):
        return myList[-1]
    before = myList[pos - 1]
    after = myList[pos]
    if after - myNumber < myNumber - before:
       return after
    else:
       return before

# locl and glob binning
def gen_binned(fluxes, phases, loclinptbins=loclsize, globinptbins=globsize, save=True):
    
    pathsave = os.environ['EXOP_DATA_PATH'] + '/tess/locl_v_glob.pickle'


    numbdata = len(fluxes)


    if not os.path.exists(pathsave) or overwrite:
        # holder np arrays
        inptloclfold = np.empty((numbdata, loclinptbins))
        inptglobfold = np.empty((numbdata, globinptbins))
        
        xfoldlocl = np.empty((numbdata, loclinptbins))
        xfoldglob = np.empty((numbdata, globinptbins))

        # let our runner know what is happening :)
        print("\nGenerating binned")


        # for each curve in the inpt space
        for k in trange(numbdata):
            
            # assert((phases[k] == np.sort(phases[k])).all())
            
            newZero = takeClosest(phases[k],0)
            midpoint = np.where(phases[k] == newZero)[0][0]
            
            indices = range(int(midpoint-loclinptbins/2),int(midpoint+loclinptbins/2))

            # POTENTIALLY DEALING WITH UNBINNED LIGHT CURVES

            inptloclfold[k,:] = fluxes[k].take(indices)
            # print(fluxes[k][::int(fluxes[k]/globinptbins)][:globinptbins])
            inptglobfold[k,:] = fluxes[k][::int(len(fluxes[k])/globinptbins)][:globinptbins]

            xfoldlocl[k,:] = phases[k].take(indices)
            xfoldglob[k,:] = phases[k][::int(len(fluxes[k])/globinptbins)][:globinptbins]

            if k < 10:
                # print("Where values are NaNs:", np.where(np.isnan(fluxes[k].take(indices))))
                pass

        listdata = [inptloclfold, inptglobfold, xfoldlocl, xfoldglob]

        print ('Writing to %s...' % pathsave)
        objtfile = open(pathsave, 'wb')
        pickle.dump(listdata, objtfile, protocol=pickle.HIGHEST_PROTOCOL)
        objtfile.close()


    else:
        objtfile = open(pathsave, 'rb')
        print ('Reading from %s...' % pathsave)
        listdata = pickle.load(objtfile)
        objtfile.close()

    return listdata



# -----------------------------------------------------------------------------------


# graphs inputs, and transformed inputs
def inpt_before_train(locl, glob, loclx, globx, legd, labl, num_graphs=10, save=True, overwrite=True):
    """
    Takes the binned data from gen_binned and makes input graphs
    Shows both the local and global view
    """

    indxdata = np.arange(len(labl))
 
    # gives just num_graphs # of plots
    indexer = int(len(indxdata)/num_graphs)
    indexes = indxdata[0::indexer]

    # let the user know what is happening :)
    print("\nMaking input graphs!")

    # let the user know with a progressbar :)
    # for just the 10 specified plots:
    for k in tqdm(indexes):

        # red is relevant (has an output that signifies a planet is present)
        if labl[k] == 1:
            colr = 'r'
            relevant = True
        # blue is irrelevant
        else:
            colr = 'b'
            relevant = False
        
        if relevant:
            textbox = 'Relevant'
        else:
            textbox = 'Irrelevant'

        textbox += '_{}'.format(legd[k])

        # line for local, line for global [line is used liberally, just a collection of x and y points]
        # k indexes in for a SINGLE light curve
        localline = (loclx[k], locl[k, :])
        globalline = (globx[k], glob[k, :])

        # make the 2 subplots
        fig, axis = plt.subplots(2, 1, constrained_layout=True, figsize=(12,6))

        # plot 0 is the local plot, plot 1 is the global
        axis[0].plot(localline[0], localline[1], marker='o', alpha=0.6, color=colr, ls='', markersize=3)
        axis[1].plot(globalline[0], globalline[1], marker='o', alpha=0.6, color=colr, ls='', markersize=3)
        
        axis[0].set_title('Local ' + textbox)
        axis[1].set_title('Global ' + textbox)

        axis[0].set_xlabel('Phase')
        axis[0].set_ylabel('Binned Flux')

        axis[1].set_xlabel('Phase')
        axis[1].set_ylabel('Binned Flux')


        plt.tight_layout()

        if save:
            with cd(os.environ['EXOP_DATA_PATH'] + '/tess/plot/inptlabl/'):
                print ('Writing to %s...' % textbox+ ', {}'.format(k))
            
                plt.savefig(textbox+ '_{}'.format(k))
        
        else:
            plt.show()
                

    return None    


# -----------------------------------------------------------------------------------



def train_2inpt_model(model, epochs, locl, glob, labls, callbacks_list, init_epoch=0, disp=True):


    inptL1 = locl[:,:,None]
    inptG1 = glob[:,:,None]
    outp1 = labls


    hist = model.fit([inptL1, inptG1], outp1, epochs=epochs, validation_split=fractest, verbose=1, callbacks=callbacks_list, initial_epoch=init_epoch)
    
    if disp:
        print(hist.history)



# -----------------------------------------------------------------------------------


# WILL NEED TO INCLUDE HYPERPARAMETERS HERE TO DIFFERENTIATE MATRICES
# also include the [EXOP_] path here!!!
pathsavematr = os.environ['EXOP_DATA_PATH'] + '/tess/matr/' + '{}'.format(str(modl.__name__)) + '.pickle'



def matr_2inpt(model, locl, glob, labls, modl):
    

    if not os.path.exists(pathsavematr) or overwrite:
        #implement a lot of printing in this

        numbdatatest = int(fractest * len(locl))


        # separate the training from the testing
        inpttestL = locl[:numbdatatest, :]
        inpttranL = locl[numbdatatest:, :]

        inpttestG = glob[:numbdatatest, :]
        inpttranG = glob[numbdatatest:, :]

        outptest = labls[:numbdatatest]
        outptran = labls[numbdatatest:]


        numbepoc = len(os.listdir(os.environ['EXOP_DATA_PATH']+'/tess/models/{}/'.format(str(modl.__name__))))
        indxepoc = np.arange(numbepoc)


        # initialize the matrix holding all metric values
        # INDEX 1: which epoch
        # INDEX 2: which threshold value is being tested against
        # INDEX 3: [IN THIS ORDER] precision, accuracy, recall (numerical values)
        # INDEX 4: train [0] test [1]
        metr = np.zeros((numbepoc, len(thresh), 3, 2)) - 1

        # we also want the confusion matrices for later use
        # INDEX 1: which epoch
        # INDEX 2: which threshold value is being tested against
        # INDEX 3: [IN THIS ORDER] trne, flpo, flne, trpo
        # INDEX 4: train [0] test [1]
        conf_matr_vals = np.zeros((numbepoc, len(thresh), 4, 2))


        for epoc in tqdm(indxepoc):

            # train and then test 
            for i in range(2):
                # i == 0 -> train
                # i == 1 -> test

                if i == 0:
                    inptL = inpttranL
                    inptG = inpttranG
                    outp = outptran
                    
                    inptL = inptL[:, :, None]
                    inptG = inptG[:, :, None]

                    

                    
                else:
                    inptL = inpttestL
                    inptG = inpttestG
                    outp = outptest
                    
                    inptL = inptL[:, :, None]
                    inptG = inptG[:, :, None]

                    


                    # only now, within the testing parameters, we test against a range of threshold values
                    for threshold in range(len(thresh)):

                        outppred = (model.predict([inptL, inptG]) > thresh[threshold]).astype(int)

                        matrconf = confusion_matrix(outp, outppred)

                        if matrconf.size == 1:
                            matrconftemp = np.copy(matrconf)
                            matrconf = np.empty((2,2))
                            matrconf[0,0] = matrconftemp

                        if threshold == len(thresh) or threshold == 0 or threshold == len(thresh)/2:
                            print('\nMatrconf: ', matrconf)

                        trne = matrconf[0,0]
                        flpo = matrconf[0,1]
                        flne = matrconf[1,0]
                        trpo = matrconf[1,1]
                        
                        # update conf matrix holder
                        conf_matr_vals[epoc, threshold, 0, i] = trne
                        conf_matr_vals[epoc, threshold, 1, i] = flpo
                        conf_matr_vals[epoc, threshold, 2, i] = flne
                        conf_matr_vals[epoc, threshold, 3, i] = trpo


                        # update metr with only viable data (test for positive values)
                        if float(trpo + flpo) > 0:
                            metr[epoc, threshold, 0, i] = trpo / float(trpo + flpo) # precision
                        else:
                            pass

                        if float(trpo+flpo+trne) != 0:
                            metr[epoc, threshold, 1, i] = float(trpo + trne)/(trpo + flpo + trne) # accuracy
                        else:
                            pass

                        if float(trpo + flne) > 0:
                            metr[epoc, threshold, 2, i] = trpo / float(trpo + flne) # recall
                        else:
                            pass 


        listdata = [metr, conf_matr_vals]


    
        print ('Writing to %s...' % pathsavematr)
        objtfile = open(pathsavematr, 'wb')
        pickle.dump(listdata, objtfile, protocol=pickle.HIGHEST_PROTOCOL)
        objtfile.close()

    else:
        objtfile = open(pathsavematr, 'rb')
        print ('Reading from %s...' % pathsavematr)
        listdata = pickle.load(objtfile)
        objtfile.close()
    

    return listdata


# -----------------------------------------------------------------------------------


# graphs prec vs recal 
def graph_PvR(model, locl, glob, labl, metr, modl):


    numbdatatest = int(fractest * len(locl))

    # TEMP: ONLY USING THE TEST DATA
    inptL = locl[:numbdatatest,:,None]
    inptG = glob[:numbdatatest,:,None]
    outp = labl

    y_pred = model.predict([inptL, inptG])
    print('model predict: ', y_pred)
    y_real = outp[:numbdatatest]
    print('real vals: ', y_real)
    try:
        auc = roc_auc_score(y_real, y_pred)
    except:
        print('y_pred is bad :(')
        auc = 0.

    textbox = r'$\mathrm{AUC}=%.8f$' % (auc, )
        """'\n'.join((
        # r'$\mathrm{Signal:Noise}=%.2f$' % (dept/nois, ),
        # r'$\mathrm{Gaussian Standard Deviation}=%.2f$' % (auc, ),
        'Properties',
        r'$\mathrm{AUC}=%.8f$' % (auc, ))) # ,
        # r'$\mathrm{Depth}=%.4f$' % (dept, )))"""
    



    fig, axis = plt.subplots(constrained_layout=True, figsize=(12,6))


    numbepoc = len(os.listdir(os.environ['EXOP_DATA_PATH'] + 'tess/models/{}/'.format(str(modl.__name__))))
    indxepoc = np.arange(numbepoc)


    for epoc in tqdm(indxepoc):
        for i in range(2):
            
            x_points = []
            y_points = []

            if i == 0:
                typstr = 'test'
                colr = 'm'

            else:
                typstr = 'train'
                colr = 'g'


            # print("Epoch: {0}, ".format(epoc) + typstr) 


            for threshold in range(len(thresh)):
                
                x, y = metr[epoc, threshold, 2, i], metr[epoc, threshold, 0, i]

                if threshold > len(thresh)/1.1:
                    print('\nx: ', x, '\ny: ', y)
                
                # if not np.isnan(x) and x != 0 and not np.isnan(y) and y != 0:
                x_points.append(x) # recall
                y_points.append(y) # precision
                    
            axis.plot(x_points, y_points, marker='o', ls='', markersize=3, alpha=0.6, color=colr)


    
    axis.axhline(1, alpha=.4)
    axis.axvline(1, alpha=.4)
    props = dict(boxstyle='round', alpha=0.4)
    axis.text(0.05, 0.25, textbox, transform=axis.transAxes, fontsize=14, verticalalignment='top', bbox=props)
    plt.tight_layout()
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision v Recall')



    plt.savefig(os.environ['EXOP_DATA_PATH'] + '/tess/plot/PvR/' + '{0}.pdf'.format(modl.__name__))
    plt.close()
    
    return None


# -----------------------------------------------------------------------------------


def graph_conf(model, locl, glob, labl, conf):


    fig, axis = plt.subplots(2, 2, constrained_layout=True, figsize=(12,6))

    numbepoc = len(os.listdir(os.environ['EXOP_DATA_PATH'] + '/tess/models/{}/'.format(str(modl.__name__))))
    indxepoc = np.arange(numbepoc)

    print("Graphing inpt based on conf_matr") 
    
    shape1 = 'v'

    # constant threshold needed to get just one set of values\ unneeded?
    const_thresh = 70

    for epoch in tqdm(indxepoc):


        trne = conf[epoch,const_thresh,0,1]
        flpo = conf[epoch,const_thresh,1,1]
        flne = conf[epoch,const_thresh,2,1]
        trpo = conf[epoch,const_thresh,3,1]

        
        axis[0,0].plot(epoch, trne, marker=shape1, ls='', markersize=3, alpha=0.7, color='g')
        axis[0,1].plot(epoch, flpo, marker=shape1, ls='', markersize=3, alpha=0.7, color='r')
        axis[1,0].plot(epoch, flne, marker=shape1, ls='', markersize=3, alpha=0.7, color='#FFA500') # this is the color orange
        axis[1,1].plot(epoch, trpo, marker=shape1, ls='', markersize=3, alpha=0.7, color='b')

        

  
    axis[0,0].set_title('True Negative')
    axis[0,0].set_xlabel('Epoch')
    axis[0,0].set_ylabel('True Negative')

    axis[0,1].set_title('False Positive')
    axis[0,1].set_xlabel('Epoch')
    axis[0,1].set_ylabel('False Positive')

    axis[1,0].set_title('False Negative')
    axis[1,0].set_xlabel('Epoch')
    axis[1,0].set_ylabel('False Negative')

    axis[1,1].set_title('True Positive')
    axis[1,1].set_xlabel('Epoch')
    axis[1,1].set_ylabel('True Positive')

    plt.tight_layout()


    plt.savefig(os.environ['EXOP_DATA_PATH'] + '/tess/plot/Conf/' + 'inptspace_confmatr.pdf')
    plt.close()


# -----------------------------------------------------------------------------------


def main(run=True, graph=True):

    
    # data pull

    phases, fluxes, labels, legd, _, _ = retr_datatess(True, boolplot=False)

    # local and global
    loclF, globF, loclPhas, globPhas = gen_binned(fluxes, phases)


    if not os.path.exists(os.environ['EXOP_DATA_PATH'] + '/tess/models/'):
        os.makedirs(os.environ['EXOP_DATA_PATH'] + '/tess/models/')
    
    if not os.path.exists(os.environ['EXOP_DATA_PATH'] + '/tess/models/{}'.format(modl.__name__)):
        os.makedirs(os.environ['EXOP_DATA_PATH'] + '/tess/models/{}'.format(modl.__name__))

    if not os.path.exists(os.environ['EXOP_DATA_PATH'] + '/tess/matr/'):
        os.makedirs(os.environ['EXOP_DATA_PATH'] + '/tess/matr/')

    if not os.path.exists(os.environ['EXOP_DATA_PATH'] + '/tess/plot/Conf/'):
        os.makedirs(os.environ['EXOP_DATA_PATH'] + '/tess/plot/Conf/')

    if not os.path.exists(os.environ['EXOP_DATA_PATH'] + '/tess/plot/PvR/'):
        os.makedirs(os.environ['EXOP_DATA_PATH'] + '/tess/plot/PvR/')

    # load the most previous weights from last training (could make this its own function)
    try:
        weights_list = [weights for weights in os.listdir(os.environ['EXOP_DATA_PATH'] + '/tess/models/{}/'.format(modl.__name__))]
    

        if len(weights_list) > 0:
            last_epoch = max(weights_list)
        else:
            last_epoch = 0
    
    except:
        weights_list = []
        last_epoch = 0

    prevMax = 0

    # initialize model
    model = modl(loclsize, globsize, l1_param, l2_param)
    
    # something here does not work, won't load prev model correctly :(
    try:
        model.load_weights(os.environ['EXOP_DATA_PATH'] + '/tess/models/{}/'.format(modl.__name__) + last_epoch)
        print("Loading previous model's weights")

        
        regex = re.compile(r'\d+')
        prevMax = int(regex.findall(last_epoch)[0])

    except:
        print("Fresh, new model")

    modlpath = os.environ['EXOP_DATA_PATH'] + 'tess/models/{}/'.format(str(modl.__name__)) + '-{epoch:03d}' + '.h5'
    checkpoint = ModelCheckpoint(modlpath, monitor='val_acc', verbose=1, save_best_only=False, save_weights_only=False, mode='max')
    tens_board = TensorBoard(log_dir='logs/{}/{}'.format(modl.__name__,time.time()))
    callbacks_list = [checkpoint, tens_board]  

    if run:
        # need a conditional to check the shape of the model -- if two-input: use this function
        train_2inpt_model(model, numbepoc, loclF, globF, labels, callbacks_list, init_epoch=prevMax)

    if graph:
         # sample relevance graphs
        inpt_before_train(loclF, globF, loclPhas, globPhas, legd, labels, save=False)
    
    metr, conf = matr_2inpt(model, loclF, globF, labels, modl)

    if graph:
        graph_conf(model, loclF, globF, labels, conf)
        graph_PvR(model, loclF, globF, labels, metr, modl)


if __name__ == "__main__":
    main(run=False, graph=True)




"""

LOCLGLOBL GRAPHS

    check for indexing error or if NaN values are coming up as zeros

    !!!!! why are there zero values !!!!!


    deliniate region scoped in the local view onto the graph of the global
        with dashed lines
        have the points in the global (that are zoomed into for the local) as green
        have the entire local view as green


    can have localS (only if eclipsing binary, need to also be able to locate the EB...)
        local around the Secondary
        add another column to the graphs
        so like form:
                    loclP               loclS
                              Globl
    
    and localP
        local around the Primary

GENBIN:
    chew on zeros replaced with NaNs
        masked arrays
        Look in keras options for NaNs

MODEL:
    l1 l2

    allow different model input sizes
"""
=======
NO MORE SAVE WEIGHTS --> SAVE MODEL WHOLE (WE ARE LOSING METADATA)
"""
