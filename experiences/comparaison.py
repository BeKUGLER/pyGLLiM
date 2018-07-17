"""Sums up several tests on different contexts. Runs tests and saves results in json File.
Then translates this file into latex table.
"""
import os
import subprocess
import time
import warnings
from datetime import timedelta

import jinja2

from Core.dgllim import dGLLiM
from Core.gllim import GLLiM, JGLLiM, WrongContextError
from experiences import logistic
from hapke import relation_C
from tools import context
from tools.archive import Archive
from tools.experience import DoubleLearning

warnings.filterwarnings("ignore")

NOISE = 50

ALGOS_exps = [
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 1000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 1000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 500, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 500, "sigma_type": "full", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": relation_C.HapkeCRelationContext, "partiel": (0, 1, 2), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.VoieS, "partiel": (0, 1, 2, 3), "K": 300, "N": 10000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_30, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_30, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_50, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_50, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 500, "sigma_type": "iso", "gamma_type": "full"},
]


GENERATION_exps = [
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 80, "N": 5000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": None, "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"}
]

DIMENSION_exps = [
    {"context": context.InjectiveFunction(1), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(2), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(3), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(4), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(5), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(6), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

MODAL_exps = [
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 1000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]



ALGOS = ["nNG","nNdG","nNjG","NG","NdG","NjG"]
GENERATION = ["random","latin","sobol"]
DIMENSION = ["gllim"]

M_E_T = {"ALGOS":(ALGOS,ALGOS_exps,"algos.tex"),
         "GENERATION":(GENERATION,GENERATION_exps,"generation.tex"),
         "DIMENSION": (DIMENSION, DIMENSION_exps, "dimension.tex"),
         "MODAL": (["gllim"], MODAL_exps, "modal.tex")}
"""Methodes, experience , template for possible categories"""


def _load_train_gllim(i, gllim_cls, exp, exp_params, noise, method, redata, retrain, Xtest=None, Ytest=None):
    """If Xtest and Ytest are given, use instead of exp data.
    Useful to fix data across severals exp"""
    print("  Starting {} ...".format(gllim_cls.__name__))
    try:
        exp.load_data(regenere_data=redata, with_noise=noise, N=exp_params["N"], method=method)
        gllim1 = exp.load_model(exp_params["K"], mode=retrain and "r" or "l", init_local=exp_params["init_local"],
                                sigma_type=exp_params["sigma_type"], gamma_type=exp_params["gamma_type"],
                                gllim_cls=gllim_cls)
    except FileNotFoundError:
        print("\nNo model or data found for experience {}, version {} - noise : {}".format(i + 1, gllim_cls.__name__,
                                                                                           noise))
        return None
    except WrongContextError as e:
        print("\n{} method is not appropriate for the parameters ! "
              "Details \n\t{} \n\tIgnored".format(gllim_cls.__name__, e))
        return None
    except AssertionError as e:
        print("\nTraining failed ! {}".format(e))
        return None

    ti = time.time()
    if Xtest is not None:
        exp.Xtest, exp.Ytest = Xtest, Ytest
    else:
        exp.centre_data_test()
    m = exp.mesures.run_mesures(gllim1)  # warning change Xtest,Ytest
    print("  Mesures done in {:.3f} s".format(time.time() - ti))
    return m

class abstractMeasures():
    """Runs mesures on new trained or loaded gllims"""

    CATEGORIE = None

    @classmethod
    def run(cls,train=None,run_mesure=None):
        o = cls()
        o.mesure(train,run_mesure)

    def __init__(self):
        self.experiences = M_E_T[self.CATEGORIE][1]

    def _get_train_measure_choice(self, train, run_mesure):
        imax = len(self.experiences)
        train = [train] * imax if type(train) is bool else (train or [False] * imax)
        run_mesure = [run_mesure] * imax if type(run_mesure) is bool else (run_mesure or [False] * imax)
        return train, run_mesure

    def mesure(self,train,run_mesure):
        ti = time.time()
        train, run_mesure = self._get_train_measure_choice(train, run_mesure)
        imax = len(train)
        mesures = []
        old_mesures = Archive.load_mesures(self.CATEGORIE)
        for i, exp_params, t, rm in zip(range(imax), self.experiences, train, run_mesure):
            if rm:
                print("\nMesures of experience {}/{}".format(i + 1, imax))
                exp = DoubleLearning(exp_params["context"], partiel=exp_params["partiel"], verbose=None)
                dGLLiM.dF_hook = exp.context.dF
                dic = self._dic_mesures(i,exp,exp_params,t)
            else:
                print("\nLoaded mesures {}/{}".format(i + 1, imax))
                dic = old_mesures[i]
            mesures.append(dic)
        Archive.save_mesures(mesures, self.CATEGORIE)
        print("Study carried in {} \n".format(timedelta(seconds=time.time() - ti)))


    def _dic_mesures(self,i,exp,exp_params,t):
        return {}

class AlgosMeasure(abstractMeasures):

    CATEGORIE = "ALGOS"

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        dic['nNG'] = _load_train_gllim(i, GLLiM, exp, exp_params, None, "sobol", t, t)  # no noise GLLiM
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        dic["nNdG"] = _load_train_gllim(i, dGLLiM, exp, exp_params, None, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # no noise dGLLiM
        dic["nNjG"] = _load_train_gllim(i, JGLLiM, exp, exp_params, None, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # no noise joint GLLiM
        dic["NG"] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t,Xtest=Xtest,Ytest=Ytest)  # noisy GLLiM
        dic["NdG"] = _load_train_gllim(i, dGLLiM, exp, exp_params, NOISE, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # noisy dGLLiM
        dic["NjG"] = _load_train_gllim(i, JGLLiM, exp, exp_params, NOISE, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # noisy joint GLLiM
        return dic

class GenerationMeasure(abstractMeasures):

    CATEGORIE = "GENERATION"

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        dic['sobol'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)  # sobol
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        dic['latin'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "latin", t, t,Xtest=Xtest,Ytest=Ytest)  # latin
        dic['random'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "random", t, t,Xtest=Xtest,Ytest=Ytest)  # random
        return dic

class DimensionMeasure(abstractMeasures):

    CATEGORIE = "DIMENSION"

    def _dic_mesures(self, i, exp: DoubleLearning, exp_params, t):
        dic = {"gllim": _load_train_gllim(i,GLLiM,exp,exp_params,None,"sobol",t,t)}
        return dic


class ModalMeasure(abstractMeasures):
    CATEGORIE = "MODAL"

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"gllim": _load_train_gllim(i, GLLiM, exp, exp_params, None, "sobol", t, t)}
        return dic


class abstractLatexWriter():
    """Builds latex template and runs pdflatex.
    This class transforms mesures into uniformed representation matrix, where one line represents one context.
    """

    LATEX_BUILD_DIR = "latex_build"

    latex_jinja_env = jinja2.Environment(
        block_start_string='(#',
        block_end_string='#)',
        variable_start_string='(!',
        variable_end_string='!)',
        comment_start_string='\#{',
        comment_end_string='}',
        line_statement_prefix='%%',
        line_comment_prefix='%#',
        trim_blocks=True,
        autoescape=False,
        loader=jinja2.FileSystemLoader("templates_latex"),

    )
    latex_jinja_env.globals.update(zip=zip)

    CRITERES = ["compareF", "meanPred", "modalPred", "retrouveYmean", "retrouveY", "retrouveYbest"]


    LATEX_EXPORT_PATH = "../latex/tables"
    """Saving directory for bare latex table"""

    categorie = ""
    """Also serve as Latex table reference"""

    TITLE = ""
    """Latex table title """

    DESCRIPTION = ""
    """Latex table caption"""


    @classmethod
    def render(cls, **kwargs):
        """Wrapper"""
        w = cls()
        w.render_pdf(**kwargs)

    def __init__(self):
        """

        :param categorie: Choose which type of table you want to build, one of
                - algos : compare GlliM, dGlliM, jGlliM
        """
        mesures = Archive.load_mesures(self.categorie)

        self.methodes, self.experiences, self.template = M_E_T[self.categorie]
        self.matrix = self._mesures_to_matrix(mesures)
        self.matrix = self._find_best()


    def _find_best(self):
        """Find best value for each CRITERE, line per line"""
        m = []

        def best(line):
            l = [(i, c["mean"]) for i, c in enumerate(line) if c]
            l2 = [(i, c["median"]) for i, c in enumerate(line) if c]
            b = sorted(l, key=lambda d: d[1])[0][0] if len(l) > 0 else None
            b2 = sorted(l2, key=lambda d: d[1])[0][0] if len(l2) > 0 else None
            return b, b2

        for line in self.matrix:
            for key in self.CRITERES:
                values = [case[key] if case else None for case in line]
                bmean, bmedian = best(values)
                if bmean is not None:  # adding indicator of best
                    line[bmean][key]["mean"] = (line[bmean][key]["mean"], True)
                if bmedian is not None:
                    line[bmedian][key]["median"] = (line[bmedian][key]["median"], True)
            m.append(line)
        return m

    def _mesures_to_matrix(self, mesures):
        """Put measure in visual order. needs to synchronise with header data"""
        return [[mes[meth] for meth in self.methodes] for mes in mesures]

    def _horizontal_header(self):
        return self.methodes

    def _vertical_header(self):
        # adding  dimensions
        for exp in self.experiences:
            cc = exp["context"](exp["partiel"])
            exp["D"] = cc.D
            exp["L"] = cc.L
        return self.experiences

    def render_latex(self):
        template = self.latex_jinja_env.get_template(self.template)
        CRITERES = self.CRITERES + ["validPreds"]
        baretable = template.render(MATRIX=self.matrix, title=self.TITLE, description=self.DESCRIPTION,
                                    hHeader=self._horizontal_header(), vHeader=self._vertical_header(),
                                    label=self.categorie, CRITERES=CRITERES)
        standalone_template = self.latex_jinja_env.get_template("STANDALONE.tex")
        return baretable, standalone_template.render(TABLE = baretable)

    def render_pdf(self, show_latex=False, verbose=False):
        barelatex , latex = self.render_latex()
        if show_latex:
            print(latex)

        filename = self.categorie+'.tex'
        path = os.path.join(self.LATEX_EXPORT_PATH,filename)
        with open(path,"w",encoding="utf8") as f:
            f.write(barelatex)
        cwd = os.path.abspath(os.getcwd())
        os.chdir(self.LATEX_BUILD_DIR)
        with open(filename,"w",encoding="utf8") as f:
            f.write(latex)
        command = ["pdflatex", filename] if verbose else ["pdflatex", "-interaction", "batchmode", filename]
        subprocess.run(command, check=True)
        subprocess.run(command, check=True)  # for longtable package
        os.chdir(cwd)


class AlgosLatexWriter(abstractLatexWriter):
    categorie = "ALGOS"
    TITLE = "Algorithmes"
    DESCRIPTION = "Chaque algorithme est testé avec un dictionnaire bruité ou non."


class GenerationLatexWriter(abstractLatexWriter):
    categorie = "GENERATION"
    TITLE = "Méthode de génération"
    DESCRIPTION = "Le dictionnaire d'aprentissage est généré avec différentes méthodes de génération " \
                  "de nombres aléatoires."


class DimensionLatexWriter(abstractLatexWriter):
    categorie = "DIMENSION"
    TITLE = "Influence de la dimension"
    DESCRIPTION = "La même fonction générique est apprise et inversée pour différentes dimensions."

    def _mesures_to_matrix(self, mesures):
        return [[mes["gllim"] for mes in mesures]]

    def _horizontal_header(self):
        return super()._vertical_header()

    def _vertical_header(self):
        return [self.experiences[0]]


class ModalLatexWriter(abstractLatexWriter):
    categorie = "MODAL"
    TITLE = "Mode de prévision"
    DESCRIPTION = "Comparaison des résultats de la prévision par la moyenne (Me,Yme) " \
                  "par rapport à la prévision par le mode (Mo,Ymo,Yb)"


# run_self.mesures(train=[False] *  13 + [True] * 2 ,
#             run_mesure=[False] * 13 + [True] * 2 )
# mesuresAlgos(train=False,run_mesure=False)
# GenerationMeasure.run(train=False,run_mesure=True)

def main():
    print("Launching tests...\n")
    # AlgosMeasure.run(True,True)
    # GenerationMeasure.run(True,True)
    # DimensionMeasure.run(True,True)
    # ModalMeasure.run(True,True)
    # AlgosLatexWriter.render()
    # GenerationLatexWriter.render()
    # DimensionLatexWriter.render()
    ModalLatexWriter.render()

if __name__ == '__main__':
    main()