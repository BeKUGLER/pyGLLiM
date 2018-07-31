"""Runs severals real tests on GLLiM, sGLLiM etc... """
import time
import logging
import logging.config

import coloredlogs
import numpy as np

from Core import training
from Core.dgllim import dGLLiM
from Core.gllim import GLLiM, jGLLiM
from Core.riemannian import RiemannianjGLLiM
from experiences.rtls import RtlsCO2Context
from tools import context
from tools.archive import Archive
from tools.measures import Mesures, VisualisationMesures, MesuresSecondLearning, VisualisationSecondLearning
from tools.results import Results, VisualisationResults

Ntest = 50000

class Experience():
    context: context.abstractFunctionModel
    archive: Archive
    mesures: VisualisationMesures
    results: VisualisationResults

    def __init__(self, context_class, partiel=None, verbose=True, with_plot=False, **kwargs):
        """If with_plot is False, methods which use matplotlib or vispy can't be used.
        Used to speed up import (no costly import).
        Other keyword args are forwarded to the context object."""

        self.second_learning = None
        self.partiel = partiel
        self.verbose = verbose

        self.context = context_class(partiel,**kwargs)

        self.archive = Archive(self)
        if with_plot:
            self.mesures = VisualisationMesures(self)
            self.results = VisualisationResults(self)
        else:
            self.mesures = Mesures(self)
            self.results = Results(self)

    def load_data(self, regenere_data=False, with_noise=None, N=1000, method="sobol"):
        self.with_noise = with_noise
        self.generation_method = method
        self.N = N
        Ndata = N + Ntest

        if regenere_data:
            X, Y = self.context.get_data_training(Ndata,method=method)

            if with_noise:
                Y = self.context.add_noise_data(Y,std=with_noise)

            self.archive.save_data(X,Y)
        else:
            X,Y = self.archive.load_data()

        self.Xtrain, self.Ytrain = X[0:N], Y[0:N]
        self.Xtest, self.Ytest = X[-Ntest:], Y[-Ntest:]

        # Mean of training responses
        self.Xmean = self.Xtrain.mean(axis=0)

    @property
    def Ntest(self):
        return len(self.Ytest)

    @property
    def variables_lims(self):
        return self.context.variables_lims

    @property
    def variables_names(self):
        return self.context.variables_names

    @property
    def variables_range(self):
        return self.context.variables_range

    @property
    def meta_data(self):
        """Collect and returns meta data used for the current experiment"""
        return dict(
            with_noise=self.with_noise, N=self.N, Ntest=self.Ntest, K=self.K, Lw=self.Lw,
            sigma_type=self.sigma_type, gamma_type=self.gamma_type,
            gllim_class = self.gllim_cls.__name__, context=self.context.__class__.__name__,
            partiel=self.partiel, generation_method=self.generation_method, init_local=self.init_local,
            second_learning=self.second_learning
        )


    def get_infos(self,**kwargs):
        return dict(self.meta_data, **kwargs)


    def _load_gllim(self,params):
        """Create instance of gllim, load params and dimensions. Don't proceed to inversion."""
        gllim = self.gllim_cls(len(params["pi"]), self.Lw, sigma_type=self.sigma_type, gamma_type=self.gamma_type,
                               verbose=self.verbose)
        gllim.D = len(params["A"][0])
        L = len(params["Gamma"][0])
        gllim.D = len(params["A"][0])
        gllim.Lt = L - self.Lw
        gllim._init_from_dict(params)
        return gllim

    def load_model(self, K, Lw=0, sigma_type="full", gamma_type="full", gllim_cls=GLLiM,
                   mode="r", multi_init=True, init_local=None, track_theta=False, with_time=False):
        self.K = K
        self.Lw = Lw
        self.sigma_type = sigma_type
        self.gamma_type = gamma_type
        self.gllim_cls = gllim_cls
        if init_local is not None:
            multi_init = True
        self.multi_init = multi_init
        self.init_local = init_local

        if mode == "l": #load from memory
            params = self.archive.load_gllim()
            gllim = self._load_gllim(params)
            training_time = params["training_time"]
        elif mode == "r": # new training
            t = time.time()
            gllim = self.new_train(track_theta=track_theta)
            training_time = time.time() - t
            self.archive.save_gllim(gllim,track_theta,training_time=training_time)
        else: # only register meta-data
            return
        gllim.inversion()
        if with_time:
            return gllim, training_time
        return gllim

    def new_train(self,track_theta=False):
        if self.gllim_cls is RiemannianjGLLiM and self.multi_init:
            raise ValueError("Multi init can't be used with Manifold optimization")

        if self.init_local:
            def ck_init_function():
                return self.context.get_X_uniform(self.K)

            gllim = training.init_local(self.Xtrain, self.Ytrain, self.K, ck_init_function, self.init_local, Lw=self.Lw,
                                        sigma_type=self.sigma_type, gamma_type=self.gamma_type,
                                        track_theta=track_theta, gllim_cls=self.gllim_cls, verbose=self.verbose)
        elif self.multi_init:
            gllim = training.multi_init(self.Xtrain, self.Ytrain, self.K, Lw=self.Lw,
                                        sigma_type=self.sigma_type, gamma_type=self.gamma_type,
                                        track_theta=track_theta, gllim_cls=self.gllim_cls, verbose=self.verbose)
        else:
            gllim = training.basic_fit(self.Xtrain, self.Ytrain, self.K, Lw=self.Lw,
                                       sigma_type=self.sigma_type, gamma_type=self.gamma_type,
                                       track_theta=track_theta, gllim_cls=self.gllim_cls, verbose=self.verbose)
        return gllim

    def centre_data_test(self):
        self.Xtest = self.Xtest * 0.8 + (self.context.variables_lims[:, 1] - self.context.variables_lims[:, 0]) / 10
        self.Ytest = self.context.F(self.Xtest)


    def clean_X(self,X,as_np_array=False):
        mask = self.context.is_X_valid(X)
        if type(X) is list:
            X = [x[m] for x, m in zip(X, mask) if (m is not None and len(x[m]) > 0)]  # at least one x is ok
        else:
            X = X[mask]
        if as_np_array:
            X = np.array(X)
        return X , mask

    @staticmethod
    def get_nb_valid(mask):
        return sum(m.sum() if m is not None else 0 for m in mask) / sum(len(m) if m is not None else 1 for m in mask)


    def clean_modal_prediction(self, G:GLLiM, nb_component=None, threshold=None):
        """Modal predicts and removes theoretically absurd prediction"""
        t = time.time()
        X, _, weights = G.modal_prediction(self.Ytest, components=nb_component, threshold=threshold, sort_by="weight")

        if self.verbose:
            logging.debug("Gllim modal prediction done in {:.2f} secs".format(time.time() - t))

        X , mask = self.clean_X(X)
        nb_valid = self.get_nb_valid(mask)
        mask = [(m is not None and sum(m, 0) > 0) for m in mask]  # only X,Y for which at least one prediction is clean
        return X, self.Ytest[mask], self.Xtest[mask], nb_valid


    def _one_X_prediction(self, gllim: GLLiM, Y, method):
        if method == "mean":
            X = gllim.predict_high_low(Y)
        elif method == "bestY":
            X = self.best_Y_prediction(gllim, Y)
        else:
            if method == "height":
                Xlist, _ , _  = gllim.modal_prediction(Y, components=1,sort_by="height")
            elif method == "weight":
                Xlist, _, _ = gllim.modal_prediction(Y, components=1, sort_by="weight")
            else:
                raise ValueError("Unknow prediction method")
            X = np.array([xs[0] for xs in Xlist])
        return X

    def compute_FXs(self, Xs, ref_function=None):
        ref_function = ref_function or self.context.F
        N = len(Xs)
        cumlenths = np.cumsum([len(X) for X in Xs])
        Xglue = np.array([x for X in Xs for x in X])
        Yall = ref_function(Xglue)
        Ys = []
        for i in range(N):
            debut = 0 if i == 0 else cumlenths[i - 1]
            fin = cumlenths[i]
            Ys.append(Yall[debut:fin])
        return Ys

    def best_Y_prediction(self, gllim: GLLiM, Y, ref_function=None):
        """Compute modal prediction then choose x for which F(x) is closer to y"""
        Xlist, _, _ = gllim.modal_prediction(Y, components=10, sort_by="weight")
        Ylist = np.array(self.compute_FXs(Xlist, ref_function=ref_function))
        indexes = np.abs(Ylist - Y[:, :, None]).max(axis=2).argmin(axis=1)
        mask = [i == np.arange(10) for i in indexes]
        return np.array(Xlist)[mask]


    def reconstruct_F(self,gllim,X):
        clusters, rnk = gllim.predict_cluster(X, with_covariance=False)
        N, _ = X.shape
        # Mean estimation
        Y_estmean = np.empty((N, gllim.D))
        for n, xn in enumerate(X):
            Y_estmean[n] = np.sum(rnk[n][:, None] * (np.matmul(gllim.AkList, xn) + gllim.bkList), axis=0)

        return Y_estmean, rnk


class SecondLearning(Experience):
    """Implements double learning methods"""

    mesures: MesuresSecondLearning

    @classmethod
    def from_experience(cls, exp: Experience, number=1, with_plot=False):
        """Promote exp to SecondLearning"""
        exp.__class__ = cls
        exp.number = number
        exp.mesures = VisualisationSecondLearning(exp) if with_plot else MesuresSecondLearning(exp)

        return exp

    def __init__(self, context_class, number=1, partiel=None, verbose=True, with_plot=False, **kwargs):
        """number allows several second learning with the same first learning."""
        super().__init__(context_class, partiel=partiel, verbose=verbose, with_plot=with_plot, **kwargs)
        self.number = number
        self.mesures = MesuresSecondLearning(self)

    def _predict_sample_parallel(self, gllim: GLLiM, Y, nb_per_Y, K):
        Xs = gllim.predict_sample(Y,nb_per_Y=nb_per_Y)
        newXYK, Yclean, mask = [], [], []
        for xadd , y in zip(Xs,Y):
            xadd , _ = self.clean_X(xadd,as_np_array=True)
            is_ok = len(xadd) > 0
            if is_ok:
                yadd = self.context.F(xadd)
                if self.with_noise:
                    yadd = self.context.add_noise_data(yadd,std= self.with_noise)
                newXYK.append((xadd,yadd,K))
                Yclean.append(y)
            mask.append(is_ok)
        return newXYK, np.array(Yclean), mask

    def extend_training_parallel(self, gllim: GLLiM, Y=None, X=None, nb_per_Y=1000, clusters=50):
        self.second_learning = "perY:{},{}".format(nb_per_Y, clusters)

        if Y is None:
            Y = self.Ytest
            X = self.Xtest

        t = time.time()
        logging.info("Modal prediction and data preparation...")
        newXYK, Y, mask = self._predict_sample_parallel(gllim, Y, nb_per_Y, clusters)
        X = X[mask] if X is not None else None
        logging.info("Modal prediction done in {0:.2f} secs".format(time.time() - t))

        gllims = training.second_training_parallel(newXYK, Lw=self.Lw, sigma_type=self.sigma_type,
                                                   gamma_type=self.gamma_type)

        self.archive.save_second_learned(gllims,Y,X)

        return Y,X,gllims

    def load_second_learning(self, nb_per_Y, clusters, withX=True):
        self.second_learning = "perY:{},{}".format(nb_per_Y, clusters)
        Y, X , thetas = self.archive.load_second_learned(withX)
        gllims = []
        self.verbose, old_verbose = None, self.verbose
        t = time.time()
        logging.info("Loading and inversion of second learning gllims...")
        for theta in thetas:
            gllim = self._load_gllim(theta)
            gllim.inversion()
            gllims.append(gllim)
        logging.info("Done in {0:.2f} secs".format(time.time() - t))
        self.verbose = old_verbose
        return Y, X , gllims


# def monolearning():
#     exp = SecondLearning(context.LabContextOlivine, partiel=(0, 1, 2, 3))
#     exp.load_data(regenere_data=False, with_noise=50, N=100001, method="sobol")
#     exp.Xtrain = exp.Xtrain[:,(0,)]
#     gllim = exp.load_model(100, retrain=False, with_GMM=True, track_theta=True, init_uniform_ck=False)
#     exp.context.partiel = (0,)
#     exp.mesures.correlations2D(gllim, exp.context.get_observations(), exp.context.wave_lengths, 1, method="mean")


def double_learning(Ntest=200):
    exp = Experience(context.LabContextOlivine, partiel=(0, 1, 2, 3), with_plot=False)
    exp.load_data(regenere_data=False, with_noise=50, N=10000, method="sobol")
    dGLLiM.dF_hook = exp.context.dF
    # X, _ = exp.add_data_training(None,adding_method="sample_perY:9000",only_added=False,Nadd=132845)
    gllim = exp.load_model(200, mode="l", track_theta=False, init_local=200,
                           sigma_type="full", gamma_type="full", gllim_cls=jGLLiM)

    exp.centre_data_test()
    exp.Xtest, exp.Ytest = exp.Xtest[0:Ntest], exp.Ytest[0:Ntest]

    d1 = exp.mesures.run_mesures(gllim)

    exp = SecondLearning.from_experience(exp, with_plot=True)
    exp.extend_training_parallel(gllim, Y=exp.Ytest, X=exp.Xtest, nb_per_Y=10000, clusters=100)
    Y, X, gllims = exp.load_second_learning(10000, 100, withX=True)

    d2 = exp.mesures.run_mesures(gllims, Y, X)
    exp.archive.save_mesures({"first": d1, "second": d2, "Ntest": Ntest}, "SecondLearning")

    # savepath = "/scratch/WORK/sequence2D"
    # exp.mesures.compare_density2D_parallel(Y[0:2], gllim, gllims[0:2], X=X[0:2], savepath=savepath)
    # exp.mesures.G.load_interactive_fig(savepath)
    index = 3
    # X0 = exp.Xtest[56]
    # Y0 = exp.context.F(X0[None, :])
    # exp.mesures.plot_conditionnal_density(gllim, Y0, None, sub_densities=4, with_modal=True, colorplot=True)

    # modals, _ , weights = gllim.modal_prediction(exp.context.get_observations(), threshold=0.0001)
    # Xw_clus = clustered_mean(modals,[w for p in weights for h,w in p])
    # Xh_clus = clustered_mean(modals,[h for p in weights for h,w in p])

    # MCMC_X, Std = exp.context.get_result()

    # exp.mesures.plot_density_sequence(gllim,exp.context.get_observations(), exp.context.wave_lengths,
    #                                   index=index,Xref=MCMC_X,StdRef=Std,with_pdf_images=True,varlims=(-0.2,1.2),regul="exclu")


    # exp.mesures.plot_density_sequence_parallel(gllims,Y, exp.context.wave_lengths,
    #                                  Xref= MCMC_X,StdRef=Std,with_pdf_images=True,index=index,varlims=(-0.2,1.2),
    #                                            regul="exclu")

    # exp.mesures.plot_density_sequence_clustered(gllim,exp.context.get_observations(),Xw_clus,Xh_clus,
    #                                             exp.context.wave_lengths, index=index,
    #                                             Xref=MCMC_X,StdRef=Std,with_pdf_images=True,varlims=(-0.2,1.2))


def test_map():
    exp = Experience(context.HapkeContext, partiel=(0, 1, 2, 3), with_plot=True)
    exp.load_data(regenere_data=False, with_noise=50, N=10000, method="sobol")
    dGLLiM.dF_hook = exp.context.dF
    gllim = exp.load_model(100, mode="l", track_theta=False, init_local=200,
                           gllim_cls=jGLLiM)

    Y = exp.context.get_observations()
    latlong, mask = exp.context.get_spatial_coord()
    Y = Y[mask]  # cleaning
    MCMC_X, Std = exp.context.get_result(with_std=True)
    MCMC_X = MCMC_X[mask]

    exp.results.map(gllim, Y, latlong, 0, Xref=MCMC_X)


def main():
    exp = Experience(context.LabContextOlivine, partiel=(0, 1, 2, 3), with_plot=True)

    exp.load_data(regenere_data=False, with_noise=50, N=1000, method="sobol")
    gllim = exp.load_model(10, mode="l", track_theta=False, init_local=200,
                           sigma_type="full", gamma_type="full", gllim_cls=jGLLiM)

    MCMC_X, Std = exp.context.get_result()
    exp.results.plot_density_sequence(gllim, exp.context.get_observations(), exp.context.wave_lengths,
                                      index=0, Xref=MCMC_X, StdRef=Std, with_pdf_images=True,
                                      varlims=(-0.2, 1.2), regul=True, xtitle="wavelength (microns)")



def glace():
    exp = SecondLearning(context.VoieS, partiel=(0, 1, 2, 3))
    exp.load_data(regenere_data=False,with_noise=50,N=10000,method="sobol")
    dGLLiM.dF_hook = exp.context.dF
    # X, _ = exp.add_data_training(None,adding_method="sample_perY:9000",only_added=False,Nadd=132845)
    gllim = exp.load_model(300,mode="l",track_theta=False,init_local=500,
                           sigma_type="iso",gamma_type="full",gllim_cls=dGLLiM)


    index = 0
    #
    # # MCMC_X, Std = exp.context.get_result()
    #
    # for i in [0,100,300,700,900]:
    Y , mask = exp.context.get_observations_fixed_coord(900)
    #     Y = Y[mask]
    #     # print(len(mask))
    exp.mesures.plot_density_sequence(gllim,Y, exp.context.wave_lengths,
                                      index=index,Xref=None,StdRef=None,with_pdf_images=False,varlims=(0.7,1.2),
                                      regul="exclu")
        # savepath = "VoieS_spatial{}.png".format(i)
        # exp.mesures.prediction_by_components(gllim, Y, exp.context.wave_lengths, regul="exclu",
        #                                      varlims=[(0.7,1),(0,30),(0,1),(0,1)],filename=savepath)


    # exp.mesures.plot_mesures(gllim)

    # Y , maskY = exp.context.get_observations_fixed_wl(10)
    # latlong , maskS = exp.context.get_spatial_coord()
    # mask = maskS * maskY
    # latlong = latlong[mask]
    # Y = Y[mask]
    # MCMC_X ,Std = exp.context.get_result(with_std=True)
    # MCMC_X = MCMC_X[mask]
    # Std = Std[mask]

    # exp.mesures.plot_density_sequence(gllim,Y[0:10],np.arange(10),index=0,Xref=MCMC_X[0:10],StdRef=Std[0:10])

    # exp.mesures.map(gllim,Y,latlong,0,Xref = None)


def RTLS():
    exp = Experience(RtlsCO2Context, partiel=(0, 1, 2, 3))
    exp.load_data(regenere_data=True,with_noise=50,N=10000)
    dGLLiM.dF_hook = exp.context.dF
    gllim = exp.load_model(500,mode="r",track_theta=False,init_local=500,
                           sigma_type="iso",gamma_type="full",gllim_cls=dGLLiM)

    # exp.mesures.plot_mesures(gllim)
    Xmean, Covs = exp.mesures.prediction_by_components(gllim, exp.context.get_observations(), exp.context.wave_lengths,
                                         regul="exclu",varlims=[(0.5,1),(0,30),(0,1),(0,1)])

    exp.archive.save_resultat({"w_mean":Xmean[:,0],"w_var":Covs[:,0,0],
                      "theta_mean": Xmean[:, 1], "theta_var": Covs[:, 1, 1],
                      "b_mean": Xmean[:, 2], "b_var": Covs[:, 2, 2],
                      "c_mean": Xmean[:, 3], "c_var": Covs[:, 3, 3],
                      })


def job():
    coloredlogs.install(level=logging.DEBUG, fmt="%(module)s  %(asctime)s : %(levelname)s : %(message)s",
                        datefmt="%H:%M:%S")
    double_learning()

if __name__ == '__main__':
    coloredlogs.install(level=logging.DEBUG, fmt="%(module)s %(asctime)s : %(levelname)s : %(message)s",
                        datefmt="%H:%M:%S")
    # RTLS()
    # main()
    # monolearning()
    # test_map()
    double_learning()
    # glace()
    # test_map()
