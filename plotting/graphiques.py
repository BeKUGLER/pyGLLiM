import logging
import pickle

import PIL
import dill
import matplotlib
import numpy as np
import vispy.plot, vispy.io
from cartopy import crs
from matplotlib.figure import Figure

from matplotlib import cm, ticker, transforms, rc, axes
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.patches

from plotting.interaction import AxesSequence, SubplotsSequence, vispyAnimation, mplAnimation


def _latex_relative_error(est,true):
    return r"Relative error : $|| {est} - {true}||_{{\infty}} }}$". \
        format(est=est,true=true)

def _get_rows_columns(N,coeff_row = 5, coeff_column=5):
    """Helper to position abritary number of subplots"""
    nb_row = np.ceil(np.sqrt(N))
    nb_column = np.ceil(N / nb_row)
    figsize= (nb_column * coeff_column,nb_row * coeff_row)
    return int(nb_row), int(nb_column), figsize


def overlap_colors(rnk, with_base=False):
    """Mixes base colours according to cluster importance (given by rnk).
    rnk shape : (N,K)"""
    _, K = rnk.shape
    base_colours = cm.rainbow(np.arange(K) / K)
    rn = rnk.sum(axis=1)
    c = rnk.dot(base_colours) / rn[:, None]
    c[:, 3] = (rn <= 1) * rn + (rn > 1) * 1
    if with_base:
        return c, base_colours
    return c


def load_interactive_fig(savepath):
    with open(savepath + ".dill", "rb") as f:
        fig = dill.load(f)
    fig.show()
    # pyplot.show()


class abstractDrawer:

    def __init__(self, *args, title="", savepath=None, context=None, draw_context=False,
                 write_context=False, custom_context=None):
        self.create_figure(*args)
        logging.debug("Drawing...")

        self.set_title(title, context, draw_context, custom_context)
        self.main_draw(*args)

        if write_context and savepath:
            self.write_context(context, custom_context, savepath)

        if savepath:
            self.save(savepath)

    def create_figure(self, *args):
        self.fig = None

    def main_draw(self, *args):
        pass

    def set_title(self, title, context, draw_context, custom_context):
        pass

    @staticmethod
    def _format_context(context):
        """Retuns a latex string which describes metadata."""
        context["with_noise"] = "-" if context["with_noise"] is None else context["with_noise"]
        s = """
        Data $\\rightarrow N_{{train}}={N}$ ; $N_{{test}}={Ntest}$ ; Noise : {with_noise} ; 
                Context : {context} ; Partial : {partiel} ;  Generation : {generation_method} 
        Estimator $\\rightarrow$ Class : {gllim_class} ; Second learning : {second_learning}.
        Constraints $\\rightarrow$ $\Sigma$ : {sigma_type} ; $\Gamma$  : {gamma_type}. 
        Mixture $\\rightarrow$ $K={K}$ ; $L_{{w}}$={Lw} ; Init with local cluster : {init_local}"""
        return s.format(**context)

    @classmethod
    def write_context(cls, context, custom_context, savepath):
        context = custom_context or cls._format_context(context)
        with open(savepath[:-4] + ".tex", "w") as f:
            f.write(context)

    def save(self, savepath):
        pass


class abstractDrawerMPL(abstractDrawer):
    FIGURE_TITLE_BOX = dict(boxstyle="round", facecolor='#D8D8D8',
                            ec="0.5", pad=0.5, alpha=1)

    Y_TITLE_BOX_WITH_CONTEXT = 1.2
    Y_TITLE_BOX_WITHOUT_CONTEXT = 1.05
    FIGSIZE = None

    fig: Figure

    def create_figure(self, *args):
        self.fig = pyplot.figure(figsize=self.FIGSIZE)

    def set_title(self, title, context, draw_context, custom_context):
        if custom_context is None:
            context = self._format_context(context) if context is not None else ""
        else:
            context = custom_context
        if draw_context:
            title = title + "\n" + context
        y = self.Y_TITLE_BOX_WITH_CONTEXT if draw_context else self.Y_TITLE_BOX_WITHOUT_CONTEXT
        self.fig.suptitle(title, bbox=self.FIGURE_TITLE_BOX, y=y)


    def save(self, savepath):
        self.fig.savefig(savepath, bbox_inches='tight', pad_inches=0.2)
        logging.info(f"Saved in {savepath}")
        pyplot.close(self.fig)


class clusters(abstractDrawerMPL):

    def main_draw(self, X, rnk, ck, varnames, xlims):
        colors, base_colors = overlap_colors(rnk, with_base=True)
        varx, vary = varnames
        xlim, ylim = xlims
        axe = self.fig.gca()
        axe.scatter(*X.T, c=colors, alpha=0.5, marker=".")
        axe.scatter(*ck.T, s=50, c=base_colors, marker="o")
        axe.set_xlim(*xlim)
        axe.set_ylim(*ylim)
        axe.set_xlabel(varx)
        axe.set_ylabel(vary)


class simple_plot(abstractDrawerMPL):
    MARKERS = ("." for x in iter(int, 1))

    def get_colors(self, nb):
        return cm.rainbow(np.arange(nb) / nb)

    def main_draw(self, values, labels, xlabels, ylog, xtitle, ytitle):
        rc("text", usetex=True)
        xlabels = xlabels if xlabels is not None else list(range(len(values[0])))
        axe = self.fig.gca()
        for v, lab, m, c in zip(values, labels, self.MARKERS, self.get_colors(len(values))):
            axe.scatter(xlabels, v, marker=m, label=lab, color=c)
        if ylog:
            axe.set_yscale("log")
        axe.set_ylim(np.array(values).min(), np.array(values).max())
        axe.tick_params(axis="x", labelsize=7)
        if xtitle:
            axe.set_xlabel(xtitle)
        if ytitle:
            axe.set_ylabel(ytitle)
        axe.legend()

    def save(self, savepath):
        super().save(savepath)
        rc("text", usetex=False)


class plusieursKN(simple_plot):

    @staticmethod
    def _format_context(context):
        return f"""Erreur moyenne sur {context["Ntest"]} x. \\
        Courbe 1: $K$ évolue linéairement et $N = {context["coeffNK"]} K$. \\
        Courbe 2: idem pour $K$ mais $N = {context["coeffmaxN1"]}  K_{{max}}$. \\
        Courbe 3: item pour $K$ mais $N = {context["coeffmaxN2"]}  K_{{max}}$."""


class doubleplusieursKN(plusieursKN):
    MARKERS = (s for x in iter(int, 1) for s in [".", "+"])

    def get_colors(self, nb):
        return [c for i in np.linspace(0, 1, nb // 2) for c in [cm.rainbow(i), cm.rainbow(i)]]


def _axe_schema_1D_direct(axe, ck, ckS, Ak, bk, xlims, labelcks=True):

    x_box = np.linspace(0, (xlims[1] - xlims[0]) / 50, 100)
    for k, a, b in zip(range(len(bk)), Ak[:, 0, 0], bk[:, 0]):
        x = x_box + ck[k]
        y = a * x + b
        label = "$A_{k}$" if k == 0 else None
        axe.plot(x, y, color="g", alpha=0.7, label=label)

    axe.scatter(ck, ckS, marker="+", color='r', label="$(c_{k}, c_{k}^{*})$" if labelcks else None)

class schema_1D(abstractDrawerMPL):
    Y_TITLE_BOX_WITH_CONTEXT = 1.1

    @staticmethod
    def _format_context(context):
        p = context["init_local"]
        if p is None:
            return f"Initialisation usuelle (K = { context['K'] }). Après apprentissage, $\max\limits_{{k}} \Gamma_{{k}}$ = {context['max_Gamma']:.1e}"
        else:
            return f"Initialisation avec précision = {p} (K = { context['K'] }). Après apprentissage, $\max\limits_{{k}} \Gamma_{{k}}$ = {context['max_Gamma']:.1e}"

    def main_draw(self, points_true_F, ck, ckS, Ak, bk, xlims, xtrue, ytest, modal_preds):
        axe = self.fig.add_subplot(2, 1, 1)
        axe.set_xlim(*xlims)

        axe.plot(*points_true_F, color="b", label="True F")
        _axe_schema_1D_direct(axe, ck, ckS, Ak, bk, xlims, labelcks=ytest is None)
        lhl = axe.get_legend_handles_labels()
        bbox = (0.95, 0.5)
        if ytest is not None:
            axe = self.fig.add_subplot(2, 1, 2)
            axe.scatter(ck, ckS, marker="+", color='r', label="$(c_{k}, c_{k}^{*})$")
            axe.plot(*points_true_F, color="b", label="True F")

            for i, (xpred, w) in enumerate(modal_preds):
                axe.axvline(xpred[0], color="y", linewidth=0.5,
                            label="{0:.2f} - $w_{{ {2} }} = {1:.2f}$".format(xpred[0], w, i))
                axe.annotate(str(i), (xpred[0], 0))

            axe.axhline(y=ytest, label="$y_{obs}$")
            if xtrue is not None:
                axe.axvline(xtrue, linestyle="--", color="g", alpha=0.5, label="$x_{initial}$")
            lh, ll = axe.get_legend_handles_labels()
            lhl = [lhl[0][-1]] + lh, [lhl[1][-1]] + ll
            bbox = (1.01, 0.8)
        self.fig.legend(*lhl, bbox_to_anchor=bbox)
        self.fig.subplots_adjust(right=0.77)


class IllustreCks(abstractDrawerMPL):

    def create_figure(self, *args):
        self.fig = pyplot.figure(figsize=(10, 5))

    def main_draw(self, ck, cks, alphas, points_F, points_coupe, F_label):
        axe = self.fig.add_subplot(111, projection="3d")

        axe.plot_surface(*points_F, alpha=0.4, color="gray")
        alphas = alphas / alphas.max()
        colors = cm.cool(alphas)
        axe.scatter(ck[:, 0], ck[:, 1], cks, c=colors, s=15)

        x, y, z = points_coupe
        axe.plot(x, y, z * np.ones(x.shape), color="green", alpha=1, label="$F(x) = y_{obs}$")

        fake2Dline = matplotlib.lines.Line2D([0], [0], linestyle="none", c='gray',
                                             marker='s', alpha=0.4)
        gray_patch = matplotlib.patches.Patch(color="gray", alpha=0.4)

        fake2Dline2 = matplotlib.lines.Line2D([0], [0], linestyle="none", c='cyan', marker='o')
        axe.azim, axe.elev = 83, 21  # setup view for example
        handle, label = axe.get_legend_handles_labels()
        axe.legend([gray_patch, handle[0], fake2Dline2],
                   [f"$F$ : {F_label}", label[0], "$c_{k}^{*}$"], bbox_to_anchor=[0.6, 0.15, 0.2, 0.3])
        pyplot.show()



### --------------- Plot de plusieurs subplots sur une grille ----------------- ###

class abstractGridDrawerMPL(abstractDrawerMPL):
    """Plots severals graphs on the same figure, with shared context."""

    SIZE_ROW = 5
    SIZE_COLUMN = 5

    AXES_3D = False

    def _get_nb_subplot(self, *args):
        return 1

    def _get_dims_fig(self, *args):
        nb_subplot = self._get_nb_subplot(*args)
        return _get_rows_columns(nb_subplot, coeff_row=self.SIZE_ROW, coeff_column=self.SIZE_COLUMN)

    def create_figure(self, *args):
        self.nb_row, self.nb_column, figsize = self._get_dims_fig(*args)
        self.fig = pyplot.figure(figsize=figsize)

    def save(self, savepath):
        self.fig.tight_layout(rect=[0.2, 0, 1, 1])
        super().save(savepath)

    def get_axes(self):
        projection = "3d" if self.AXES_3D else None
        axes = self.fig.subplots(self.nb_row, self.nb_column, subplot_kw={"projection": projection},
                                 squeeze=False)
        for l in axes:
            for a in l:
                yield a


class Projections(abstractGridDrawerMPL):
    """Plot X, 2 per 2 coordinates."""

    def _get_nb_subplot(self, X, labels, varnames, weights):
        L = X.shape[1]
        return L * (L - 1) // 2

    def main_draw(self, X, labels, varnames, weights):
        L = X.shape[1]
        varnames = varnames if varnames is not None else [f"x{i + 1}" for i in range(L)]

        if labels is not None:
            colors = cm.rainbow(np.linspace(0.2, 0.8, max(labels) + 1))
            colors = [colors[c] for c in labels]
        else:
            colors = [cm.rainbow(0.5)] * X.shape[0]

        if weights is not None:
            weights += 0.1
            colors = [(*c[0:3], w) for c, w in zip(colors, weights)]

        axes_iter = self.get_axes()
        for i in range(L):
            for j in range(i + 1, L):
                a = next(axes_iter)
                x = X[:, i]
                y = X[:, j]
                a.scatter(x, y, color=colors)
                a.set_xlabel(varnames[i])
                a.set_ylabel(varnames[j])
        pyplot.show()


class estimated_F(abstractGridDrawerMPL):
    AXES_3D = True

    def _get_nb_subplot(self, X, Y, Y_components, data_trueF, rnk, varnames, varlims):
        return len(Y_components)

    def main_draw(self, X, Y, Y_components, data_trueF, rnk, varnames, varlims):
        colors = "b" if rnk is None else overlap_colors(rnk)

        varx, vary = varnames
        xlim, ylim = varlims

        x, y, zs_true = data_trueF
        for g, axe in zip(Y_components, self.get_axes()):
            if len(Y_components) > 1:
                axe.set_title("Component {}".format(g))
            axe.scatter(*X.T, Y[:, g], c=colors, marker="o", s=1, alpha=0.6)
            z = zs_true[g]
            strueF = axe.plot_surface(x, y, z, color="gray", alpha=0.4, label="True F")
            axe.set_xlim(*xlim)
            axe.set_ylim(*ylim)
            axe.set_xlabel(varx)
            axe.set_ylabel(vary)


class Density1D(abstractGridDrawerMPL):
    RESOLUTION = 200
    Y_TITLE_BOX_WITH_CONTEXT = 1.18
    SIZE_COLUMN = 5

    def _get_nb_subplot(self, fs, *args):
        return len(fs)

    def main_draw(self, fs, xlims, varnames, titles,
                  modal_preds, trueXs, var_description):
        trueXs = trueXs if trueXs is not None else [None] * len(fs)

        for f, xlim, modal_pred, truex, varname, title, axe in zip(fs, xlims, modal_preds,
                                                                   trueXs, varnames, titles, self.get_axes()):
            x = np.linspace(*xlim, self.RESOLUTION)[:, None]
            y, _ = f(x)

            _axe_density_1D(axe, x.flatten(), y.flatten(), xlim,
                            varname, modal_pred, truex, title)

        self.fig.text(0.5, -0.02, var_description, horizontalalignment='center',
                      fontsize=12, bbox=self.FIGURE_TITLE_BOX, fontweight='bold')
        if fs:
            handles, labels = axe.get_legend_handles_labels()
            self.fig.legend(handles, labels, loc="upper right")


def _axe_density_1D(axe, x, y, xlims,
                    varname, modal_preds, truex, title):
    # axe.xaxis.set_minor_locator(ticker.MultipleLocator((xlims[1] - xlims[0]) / 100))
    # axe.xaxis.set_major_locator(ticker.MultipleLocator((xlims[1] - xlims[0]) / 20))
    axe.plot(x, y, "-", linewidth=1)
    axe.set_xlim(*xlims)
    axe.set_xlabel(varname)
    axe.set_title(title)

    colors = cm.Oranges(np.linspace(0.4, 0.9, len(modal_preds)))
    for i, (X, height, weight) in enumerate(modal_preds):
        axe.axvline(x=X, color=colors[i], linestyle="--",
                    label="$x_{{est}}^{{( {2} )}}$, $w_{{  {2} }} = {1:.3f}$".format(height, weight, i), alpha=0.5)

    if truex:
        axe.axvline(x=truex, label="True value", color="black", alpha=0.5)
    axe.legend()


def _axe_density2D(axe, x, y, z, colorplot, xlims, ylims,
                   varnames, modal_preds, truex, title, with_colorbar=True,
                   auto_zoom=False):
    if colorplot:
        pc = axe.pcolormesh(x, y, z, cmap="Greens")
        axe.set_xlim(*xlims)
        axe.set_ylim(*ylims)
        if with_colorbar:
            pyplot.colorbar(pc, ax=axe)
    else:
        levels = [0.001] + list(np.linspace(0, z.max(), 20))
        if auto_zoom:
            mask = z >= 0.0001  # autozoom
            lines_ok, cols_ok = mask.max(axis=1) > 0, mask.max(axis=0) > 0
            x, y, z = x[lines_ok][:, cols_ok], y[lines_ok][:, cols_ok], z[lines_ok][:, cols_ok]
        axe.contour(x, y, z, levels=levels, alpha=0.5)
    axe.set_xlabel(varnames[0])
    axe.set_ylabel(varnames[1])

    # colors = cm.coolwarm(np.linspace(0, 0.2, len(modal_preds)))
    for i, (X, height, weight) in enumerate(modal_preds):
        axe.scatter(X[0], X[1], color="black", marker=".", zorder=4,
                    label="$x_{{est}}^{{( {2} )}}$, $w_{{  {2} }} = {1:.3f}$".format(height, weight, i))
        axe.annotate(str(i), (X[0], X[1]))

    if truex is not None:
        axe.scatter(truex[0], truex[1], color="r", marker="+", label="True value", s=50, zorder=10)

    axe.set_title(title)


class Density2D(abstractGridDrawerMPL):
    RESOLUTION = 200
    SIZE_COLUMN = 5
    SIZE_ROW = 3

    def _get_nb_subplot(self, fs, varlims, varnames, titles, modal_preds, trueXs, colorplot,
                        var_description):
        return len(fs)

    def main_draw(self, fs, varlims, varnames, titles, modal_preds, trueXs, colorplot,
                  var_description):

        for f, (xlim, ylim), modal_pred, truex, varname, title, axe in zip(fs, varlims,
                                                                           modal_preds, trueXs, varnames, titles,
                                                                           self.get_axes()):
            x, y = np.meshgrid(np.linspace(*xlim, self.RESOLUTION, dtype=float),
                               np.linspace(*ylim, self.RESOLUTION, dtype=float))
            variable = np.array([x.flatten(), y.flatten()]).T
            print("Comuting of density...")
            z, _ = f(variable)
            print("Done.")
            z = z.reshape((self.RESOLUTION, self.RESOLUTION))
            _axe_density2D(axe, x, y, z, colorplot, xlim, ylim, varname,
                           modal_pred, truex, title)

        if len(fs) > 0:
            handles, labels = axe.get_legend_handles_labels()
            self.fig.legend(handles, labels, loc="upper right")

        self.fig.text(0.5, -0.02, var_description, horizontalalignment='center',
                      fontsize=12, bbox=self.FIGURE_TITLE_BOX, fontweight='bold')


class SimpleDensity2D(abstractDrawerMPL):
    RESOLUTION = 800

    def create_figure(self, *args):
        self.fig = pyplot.figure(figsize=(4, 4))

    def main_draw(self, f, varlims, varnames, mean, colorplot, title, trueX, centres):
        axe = self.fig.gca()
        xlim, ylim = varlims
        x, y = np.meshgrid(np.linspace(*xlim, self.RESOLUTION, dtype=float),
                           np.linspace(*ylim, self.RESOLUTION, dtype=float))
        variable = np.array([x.flatten(), y.flatten()]).T
        print("Comuting of density...")
        z, _ = f(variable)
        print("Done.")
        z = z.reshape((self.RESOLUTION, self.RESOLUTION))
        _axe_density2D(axe, x, y, z, colorplot, xlim, ylim, varnames,
                       (), None, title, with_colorbar=False)
        axe.scatter(*mean, label="Moyenne", marker="+", s=20, color="blue")
        axe.plot(*trueX, label="Solution théorique", color="black", linestyle="-.", alpha=0.3,
                 linewidth=0.6)
        axe.scatter(*centres.T, label="Centres", marker="+", s=20, color="green")
        axe.legend(loc="upper right")



### ----------- Sequence interactive ------------- ###

class abstractSequence(abstractDrawerMPL):
    """Switchable sequence of plots"""

    def create_figure(self, *args):
        self.axes = AxesSequence()
        self.fig = self.axes.fig()


class clusters_one_by_one(abstractSequence):

    def main_draw(self, X, rnk, ck, varnames, varlims):
        varx, vary = varnames
        xlim, ylim = varlims
        _, K = rnk.shape
        colors = cm.rainbow(np.arange(K) / K)
        for k, base_c, axe, cc in zip(range(K), colors, self.axes, ck):
            c = [(*base_c[0:3], p) for p in rnk[:, k]]
            axe.scatter(*X.T, label=str(k), c=c)
            axe.scatter(*cc, s=50, color=base_c, marker="+", label=f"c_{ {k} }")
            axe.legend()
            axe.set_xlim(*xlim)
            axe.set_ylim(*ylim)
            axe.set_xlabel(r'${}$'.format(varx))
            axe.set_ylabel(r'${}$'.format(vary))

        self.axes.show_first()
        self.fig.show()


### ------------ Histograms --------------- ###

class abstractHistogram(abstractDrawerMPL):
    TITLE = "Histogram"
    XLABEL = "x"
    LABELS = None

    Y_TITLE_BOX_WITH_CONTEXT = 1.3

    def set_title(self, title, *args):
        super().set_title(self.TITLE, *args)

    def main_draw(self, values, cut_tail, labels):
        xlabel = self.XLABEL
        if cut_tail:
            xlabel += " - Cut tail : {}%".format(cut_tail)
            values = [sorted(error)[:-len(error) * cut_tail // 100] for error in values]

        error_max = max(sum(values, []))
        bins = np.linspace(0, error_max, 1000)
        axe = self.fig.gca()
        m = len(values)
        alphas = [0.5 + i / (2 * m) for i in range(m)]
        labels = labels or self.LABELS
        for serie, alpha, label in zip(values, alphas, labels):
            axe.hist(serie, bins, alpha=alpha, label=label)
        axe.legend()
        axe.set_ylabel("Test points number")
        axe.set_xlabel(xlabel)

        means = [np.mean(s) for s in values]
        medians = [np.median(s) for s in values]

        stats = ["{0} $\\rightarrow$ Mean : {1:.2E} ; Median : {2:.2E}".format(label, mean, median)
                 for mean, median, label in zip(means, medians, labels)]
        s = "\n".join(stats)

        self.fig.text(0.5, -0.07 * m, s, horizontalalignment='center',
                      fontsize=10, bbox=dict(boxstyle="round", facecolor='#D8D8D8',
                                             ec="0.5", pad=0.5, alpha=1), fontweight='bold')


class hist_Flearned(abstractHistogram):
    TITLE = "Comparaison beetween $F$ and it's estimation"
    XLABEL = _latex_relative_error("F_{est}(x)", "F(x)")
    LABELS = ["Mean estimation"]


class hist_retrouveYmean(abstractHistogram):
    TITLE = """Comparaison beetween $Y_{obs}$ and $F(x_{pred})$ 
         for mean prediction"""
    XLABEL = _latex_relative_error("F(x_{pred})", "Y")
    LABELS = ["Cohérence (prédiction par la moyenne)"]


class hist_retrouveY(abstractHistogram):
    TITLE = """Comparaison beetween $Y_{obs}$ and $F(x_{pred})$ 
         (several $x_{pred}$ are found for each $y$)"""
    XLABEL = _latex_relative_error("F(x_{pred})", "Y")


class hist_retrouveYbest(abstractHistogram):
    TITLE = """Comparaison beetween $Y_{obs}$ and $F(x_{pred})$ 
         (best $x_{pred}$ for each $y$)"""
    XLABEL = _latex_relative_error("F(x_{pred})", "Y")


class hist_modalPrediction(abstractHistogram):
    TITLE = "Comparaison beetween X and the best modal prediction"
    XLABEL = _latex_relative_error("X_{best}", "X")


class hist_meanPrediction(abstractHistogram):
    TITLE = "Comparaison beetween X and it's mean prediction"
    XLABEL = _latex_relative_error("X_{est}", "X")


##### -------------- Animation -------------------- ####

class EvolutionCluster2D(vispyAnimation):
    INTERVAL = 0.05
    AXE_TITLE = "Clusters evolution"

    def __init__(self, points, rnks, density, xlim, ylim):
        self.points = points
        self.rnks = rnks[:, :, :100]
        self.density = density
        self.xlim = xlim
        self.ylim = ylim
        imax, _, self.K = self.rnks.shape
        super().__init__(imax)

    def init_axe(self):
        super().init_axe()
        self.line = self.axe.plot(self.points, width=0, symbol="disc", marker_size=2, edge_width=0)
        self.axe.title.text = "X clusters"
        self.axe2 = self.fig[0, 1]
        self.axe2.title.text = "X density"
        self.line2 = self.axe2.plot(self.points, width=0, symbol="disc", marker_size=2, edge_width=0)
        self._draw()

    def reset(self):
        super().reset()
        self._draw()

    def _draw(self):
        self.fig.title = "Iteration {}".format(self.current_frame)
        rnk = self.rnks[self.current_frame]
        c = overlap_colors(rnk)
        self.line._markers.set_data(pos=self.points, face_color=c, edge_color=c)
        dens = self.density[self.current_frame]
        c2 = cm.coolwarm(dens / dens.max())
        self.line2._markers.set_data(pos=self.points, face_color=c2, edge_color=c2)


class Evolution1D(mplAnimation):

    def __init__(self, points_true_F, ck, ckS, Ak, bk, xlims):
        self.points_true_F = points_true_F
        data = list(zip(ck, ckS, Ak, bk))
        super().__init__(data,xlabel="x",xlims=xlims)


    def init_animation(self):
        super().init_animation()
        xF, yF = self.points_true_F
        s = self.axe.scatter(xF, yF, marker=".", color="b", label="True F", s=0.3)
        return s,

    def update(self, frame):
        i, (ck, ckS, Ak, bk) = frame
        artists = _axe_schema_1D_direct(self.axe, ck, ckS, Ak, bk, self.xlims)
        l = self.axe.legend([f"Iteration {i}"], loc="lower left")
        # t = self.axe.text(0.01,0.01,f"Iteration {i}")
        return artists + [l]


### -------------------  Results visualisation --------------------- ###

def _prediction_1D(axe, xlim, varname, xlabels, Xmean, Xweight, xtitle, StdMean=None, Xref=None, StdRef=None,
                   modal_label=None):
    if xlim is not None:
        axe.set_ylim(*xlim)
        axe.yaxis.set_major_locator(ticker.MultipleLocator((xlim[1] - xlim[0]) / 10))

    axe.set_xlabel(xtitle, fontsize=15)
    axe.set_ylabel(varname, fontsize=20)

    if Xmean is not None:
        axe.plot(xlabels, Xmean, color="indigo", marker="*", label="Mean")

    if StdMean is not None:
        axe.fill_between(xlabels, Xmean - StdMean, Xmean + StdMean, alpha=0.3,
                         color="indigo", label="Std on mean", hatch="/")

    if Xweight is not None:
        colors = cm.Oranges(np.linspace(0.4, 0.9, Xweight.shape[1]))
        for i, X in enumerate(Xweight.T):
            label = (modal_label or "Weight prediction {}").format(i)
            axe.plot(xlabels, X, marker="+", label=label, color=colors[i])

    if Xref is not None:
        axe.plot(xlabels, Xref, color="g", marker=".", label="Reference")
    if StdRef is not None:
        axe.fill_between(xlabels, Xref + StdRef, Xref - StdRef, alpha=0.3, color="g", label="Std on reference")


class ModalPred1D(abstractDrawerMPL):
    """Draw 1D X modal pred"""

    ROW_SIZE = 5
    Y_TITLE_BOX_WITHOUT_CONTEXT = 1.01

    def main_draw(self, Xweight, Xmean, xlabels, varlim, varname, modal_label):
        axe = self.fig.gca()
        _prediction_1D(axe, varlim, varname, xlabels, Xmean, Xweight, "", modal_label=modal_label)
        axe.legend()


class Results_1D(abstractGridDrawerMPL):
    """Draw 1D prediction, with modals, reference, standard deviation"""

    ROW_SIZE = 5
    Y_TITLE_BOX_WITHOUT_CONTEXT = 1.01

    def create_figure(self, Xmean, StdMean, Xweight, xlabels, xtitle, varnames, varlims, Xref, StdRef):
        self.nb_row, self.nb_column = len(varnames), 1
        self.fig = pyplot.figure(figsize=(15, self.nb_row * self.ROW_SIZE))

    def main_draw(self, Xmean, StdMean, Xweight, xlabels, xtitle, varnames, varlims, Xref, StdRef):
        for i, axe in zip(range(self.nb_row), self.get_axes()):
            Xw = Xweight[:, :, i] if Xweight is not None else None
            xlim = varlims[i] if varlims is not None else None

            SMi = StdMean[:, i, i] if StdMean is not None else None

            Xr = Xref[:, i] if Xref is not None else None
            SRi = StdRef[:, i] if StdRef is not None else None
            _prediction_1D(axe, xlim, varnames[i], xlabels, Xmean[:, i], Xw, xtitle, StdMean=SMi,
                           Xref=Xr, StdRef=SRi)
        if self.nb_row:
            self.fig.legend(*axe.get_legend_handles_labels())  # pour ne pas surcharger


class Results_2D(abstractGridDrawerMPL):
    """Draw 2D predictions, with color as labels indicator"""

    Y_TITLE_BOX_WITHOUT_CONTEXT = 1.01
    SIZE_COLUMN = 8

    def _get_nb_subplot(self, X, xlabels, xtitle, varnames, varlims, Xref, add_data):
        n = len(varnames)
        return (2 if Xref is not None else 1) * (n * (n - 1) // 2)

    def _get_dims_fig(self, X, xlabels, xtitle, varnames, varlims, Xref, add_data):
        if Xref is None:
            return super(Results_2D, self)._get_dims_fig(X, xlabels, xtitle, varnames, varlims, Xref, add_data)
        nb_col = 2
        nb_row = self._get_nb_subplot(X, xlabels, xtitle, varnames, varlims, Xref, add_data) / nb_col
        nb_row = int(np.ceil(nb_row))
        return nb_row, nb_col, (self.SIZE_COLUMN * nb_col,
                                self.SIZE_ROW * nb_row)

    def main_draw(self, X, xlabels, xtitle, varnames, varlims, Xref, add_data):
        nb_var = len(varnames)
        add_data = add_data or {}
        indexes = [(i, j) for i in range(nb_var) for j in range(i + 1, nb_var)]
        iterator = self.get_axes()
        for i, j in indexes:
            add_curve, add_label = add_data.get((i, j), (None, ""))
            x = X[:, (i, j)]
            axe = next(iterator)
            l = axe.scatter(*x.T, c=xlabels, marker="+", label="prediction")
            if add_curve is not None:
                axe.plot(*add_curve, label=add_label)
            if Xref is not None:
                axe2 = next(iterator)
                x = Xref[:, (i, j)]
                l = axe2.scatter(*x.T, c=xlabels, marker="^", label="reference")
                if add_curve is not None:
                    axe2.plot(*add_curve, label=add_label)
                axe2.set_xlabel(varnames[i])
                axe2.set_ylabel(varnames[j])
                axe2.legend()
            if varlims is not None:
                axe.set_xlim(varlims[i])
                axe.set_ylim(varlims[j])
                if Xref is not None:
                    axe2.set_xlim(varlims[i])
                    axe2.set_ylim(varlims[j])
            axe.set_xlabel(varnames[i], fontsize=20)
            axe.set_ylabel(varnames[j], fontsize=20)
            axe.legend()
        if nb_var:
            self.fig.subplots_adjust(right=0.9)
            new_axe = self.fig.add_axes([1, 0.15, 0.04, 0.7])
            c = self.fig.colorbar(l, orientation="vertical", cax=new_axe)
            c.set_label(xtitle)


#### ------------- Density sequences ------------------ ######

class abstractGridSequence(abstractGridDrawerMPL):

    def create_figure(self, *args):
        self.nb_row, self.nb_column, figsize = self._get_dims_fig(*args)
        self.axes_seq = SubplotsSequence(self.nb_row, self.nb_column, self._get_nb_subplot(*args), figsize=figsize)
        self.fig = self.axes_seq.fig


class Density1DSequence(abstractGridSequence):
    RESOLUTION = 200
    FIGSIZE = (25, 15)
    SAVEBOUNDS = (2, 0.5, 21, 6)

    def _get_nb_subplot(self, densitys, modal_preds, xlabels, xtitle, Xmean, Xweight, xlim,
                        varname, Yref, StdRef, StdMean, images_paths):
        return images_paths and 3 or 2

    def _get_dims_fig(self, densitys, modal_preds, xlabels, xtitle, Xmean, Xweight, xlim,
                      varname, Yref, StdRef, StdMean, images_paths):
        return images_paths and (2, 2, self.FIGSIZE) or (2, 1, self.FIGSIZE)

    def main_draw(self, densitys, modal_preds, xlabels, xtitle, Xmean, Xweight, xlim,
                  varname, Yref, StdRef, StdMean, images_paths):
        if xlabels is None:
            xlabels = np.arange(len(Xmean))
        x = np.linspace(*xlim, self.RESOLUTION)[:, None]
        ydensity, _ = densitys(x)
        xpoints = x.flatten()

        for i, axes, y, m in zip(range(len(ydensity)), self.axes_seq, ydensity, modal_preds):

            _axe_density_1D(axes[0], xpoints, y.flatten(), xlim, varname, m, None, "")

            if images_paths:
                axe2 = axes[2]
                axe_im = axes[1]
                img = PIL.Image.open(images_paths[i]).convert("L")
                axe_im.imshow(np.asarray(img), cmap="gray", aspect="auto")
                axe_im.get_xaxis().set_visible(False)
                axe_im.get_yaxis().set_visible(False)
            else:
                axe2 = axes[1]

            _prediction_1D(axe2, xlim, varname, xlabels, Xmean, Xweight, xtitle,
                           StdMean=StdMean, Xref=Yref, StdRef=StdRef)

            # Current point
            axe2.axvline(xlabels[i], c="b", marker="<", label="index " + str(i), zorder=4, alpha=0.4)
            axe2.legend()
        self.axes_seq.show_first()

    def save(self, savepath):
        self.fig.show()
        pyplot.show()
        self.fig.savefig(savepath, bbox_inches=transforms.Bbox.from_bounds(*self.SAVEBOUNDS))
        logging.info(f"Saved in {savepath}")


class Density1DNappe(abstractDrawerMPL):

    def main_draw(self, densitys, modal_preds, xlabels, xtitle, Xmean, Xweight, xlim,
                  varname, Yref, StdRef, StdMean, images_paths):
        if xlabels is None:
            xlabels = np.arange(len(Xmean))
        x = np.linspace(*xlim, self.RESOLUTION)[:, None]
        ydensity, _ = densitys(x)
        xpoints = x.flatten()

        for i, axes, y, m in zip(range(len(ydensity)), self.axes_seq, ydensity, modal_preds):

            _axe_density_1D(axes[0], xpoints, y.flatten(), xlim, varname, m, None, "")

            if images_paths:
                axe2 = axes[2]
                axe_im = axes[1]
                img = PIL.Image.open(images_paths[i]).convert("L")
                axe_im.imshow(np.asarray(img), cmap="gray", aspect="auto")
                axe_im.get_xaxis().set_visible(False)
                axe_im.get_yaxis().set_visible(False)
            else:
                axe2 = axes[1]

            _prediction_1D(axe2, xlim, varname, xlabels, Xmean, Xweight, xtitle,
                           StdMean=StdMean, Xref=Yref, StdRef=StdRef)

            # Current point
            axe2.axvline(xlabels[i], c="b", marker="<", label="index " + str(i), zorder=4, alpha=0.4)
            axe2.legend()
        self.axes_seq.show_first()





class Density2DSequence(abstractGridSequence):
    """Show a sequence of conditionnal densities with 2 versions."""

    RESOLUTION = 200

    def _get_nb_subplot(self, sbefore, fsafter, varlims, *args):
        return len(varlims) * 2

    def _get_dims_fig(self, *args):
        n = self._get_nb_subplot(*args)
        return n // 4, 4, (5 * n // 4, 5 * 4)

    def get_axes(self, page_axes):
        for axe in page_axes:
            yield axe

    def main_draw(self, fsbefore, fsafter, varlims, varnames, titlesb, titlesa,
                  modal_predss_before, modal_predss_after, trueXss, colorplot):
        N = len(fsafter)
        for i, fbefore, fafter, axes, trueXs, modal_preds_before, modal_preds_after in \
                zip(range(N), fsbefore, fsafter, self.axes_seq, trueXss, modal_predss_before,
                    modal_predss_after):  # sequence of points
            iterator = self.get_axes(axes)
            for fb, fa, (xlim, ylim), modal_predb, modal_preda, \
                truex, varname, titleb, titlea in zip(fbefore, fafter, varlims, modal_preds_before, modal_preds_after,
                                                      trueXs, varnames, titlesb, titlesa):
                x, y = np.meshgrid(np.linspace(*xlim, self.RESOLUTION, dtype=float),
                                   np.linspace(*ylim, self.RESOLUTION, dtype=float))
                variable = np.array([x.flatten(), y.flatten()]).T
                za, _ = fa(variable)
                zb, _ = fb(variable)
                za = za.reshape((self.RESOLUTION, self.RESOLUTION))
                zb = zb.reshape((self.RESOLUTION, self.RESOLUTION))
                axeb = next(iterator)
                axea = next(iterator)
                _axe_density2D(axeb, x, y, zb, colorplot, xlim, ylim, varname, modal_predb, truex, titleb,
                               with_colorbar=False, auto_zoom=False)
                _axe_density2D(axea, x, y, za, colorplot, xlim, ylim, varname, modal_preda, truex, titlea,
                               with_colorbar=False, auto_zoom=False)
            logging.debug(f"Drawing of page {i+1}/{N}")
        self.axes_seq.show_first()
        pyplot.show()

    def save(self, savepath):
        s = savepath + ".dill"
        with open(s, 'wb') as f:
            pickle.dump(self.fig, f)
        logging.info(f"Dumps of interactive figure in {s}")


######  ------------------------------------ Maps ---------------------------------- #####

class MapValues(abstractDrawerMPL):
    FIGSIZE = (25, 12)

    Y_TITLE_BOX_WITHOUT_CONTEXT = 0.95

    def main_draw(self, latlong, values, addvalues, titles):
        lat = list(latlong[:, 0])
        long = list(latlong[:, 1])
        axe = self.fig.add_subplot(211, projection=crs.PlateCarree())

        totalvalues = list(values) + list([] if addvalues is None else addvalues)
        vmin, vmax = min(totalvalues), max(totalvalues)

        s = axe.scatter(long, lat, transform=crs.Geodetic(),
                        cmap=cm.rainbow, vmin=vmin, vmax=vmax,
                        c=list(values))
        axe.set_title(titles[0])

        if addvalues is None:
            self.fig.colorbar(s)
        else:
            ax2 = self.fig.add_subplot(212, projection=crs.PlateCarree())
            s2 = ax2.scatter(long, lat, transform=crs.Geodetic(), cmap=cm.rainbow, vmin=vmin, vmax=vmax,
                             c=addvalues)
            ax2.set_title(titles[1])
            self.fig.subplots_adjust(right=0.9)
            cbar_ax = self.fig.add_axes([0.65, 0.15, 0.02, 0.7])
            self.fig.colorbar(s2, cax=cbar_ax)


###   ----------------------  Vispy scatter    ---------------------- ###

class abstractDrawerVispy(abstractDrawer):
    fig: vispy.plot.Fig

    def create_figure(self, *args):
        self.fig = vispy.plot.Fig()

    def set_title(self, title, context, draw_context, custom_context):
        self.fig.title = title

    def save(self, savepath):
        image = self.fig.render()
        vispy.io.write_png(savepath, image)
        logging.info(f"Saved in {savepath}")


class abstractGridDrawerVispy(abstractDrawerVispy):

    def _get_nb_subplot(self, *args):
        return 1

    def create_figure(self, *args):
        self.nb_row, self.nb_column, _ = _get_rows_columns(self._get_nb_subplot(*args), 1, 1)
        super(abstractGridDrawerVispy, self).create_figure(*args)

    def get_axes(self):
        for i in range(self.nb_row):
            for j in range(self.nb_column):
                yield self.fig[i, j]


class ScatterProjections(abstractGridDrawerVispy):

    def _get_nb_subplot(self, points, labels, add_points):
        L = points.shape[1]
        return L * (L - 1) // 2

    def main_draw(self, X, labels, add_X):
        if labels is not None:
            colors = cm.rainbow(np.linspace(0.2, 0.8, max(labels) + 1))
            colors = [colors[c] for c in labels]
        else:
            colors = [cm.rainbow(0.7)] * X.shape[0]

        L = X.shape[1]
        axes_iter = self.get_axes()
        for i in range(L):
            for j in range(i + 1, L):
                axe = next(axes_iter)
                if add_X is not None:
                    col = cm.coolwarm(np.linspace(0, 1, 2))
                    axe.plot(add_X[0:1, (i, j)], symbol="*", face_color="yellow", marker_size=10,
                             title="x initial")
                    axe.plot(add_X[1:3, (i, j)], symbol="-", face_color=col, marker_size=10,
                             title="centres")
                    axe.plot(add_X[3:5, (i, j)], symbol="square", face_color=col, marker_size=10,
                             title="predictions")

                axe.plot(X[:, (i, j)], width=0, symbol="disc", marker_size=3, edge_width=1,
                         face_color=colors, edge_color=colors)
                axe.title.text = f"x{i} - x{j}"

        self.fig.show(run=True)




##### ----------------- TODO A refactor en classe  --------------- #################
















def trace_retrouveY(Xs,diffs):
    """Xs shape (N,nb_component,L) diffs shape (N,nb_component,D)"""
    D = diffs.shape[2]
    for i in range(Xs.shape[2]): # One variable for each figure
        fig = pyplot.figure()
        axe = fig.add_subplot(111, projection='3d')
        xs ,ys,zs = [],[],[]
        for xsn , ysn in zip(Xs,diffs):
            for x,y in zip(xsn,ysn):
                v = x[i]
                xs.extend([v] * D )
                ys.extend( list(range(D)))
                zs.extend(y)
        axe.scatter(xs,ys,zs)
    pyplot.show()








def influence_theta(B0,H):
    thetas = np.linspace(0,np.pi,200)
    b = B0 * H / ( H + np.tan(thetas/2))
    pyplot.plot(thetas,1+b)
    pyplot.xlabel(r"$\theta$ en radian")
    pyplot.ylabel(r"$1 + B$")
    pyplot.show()


def plot_Y(Y):
    """Plot each Y with a different color (geomtries in x axis)"""
    fig = pyplot.figure()
    axe = fig.gca()
    colors = cm.rainbow(np.arange(len(Y))/len(Y))
    for y,c in zip(Y,colors):
        axe.plot(y,c=c)
    pyplot.show()






class CkAnimation(mplAnimation):

    def __init__(self,cks,varnames=("x1","x2"), varlims=((0,1),(0,1))):
        super().__init__(cks,xlabel=varnames[0],ylabel=varnames[1],
                         xlims=varlims[0],ylims=varlims[1])


    def init_animation(self):
        self.ln, = self.axe.plot([], [], 'ro', animated=True)
        return self.ln ,

    def update(self,frame):
        self.ln.set_data(frame.T)
        return self.ln,



def illustre_derivative(F,dF):
    resolution = 100
    x, y = np.meshgrid(np.linspace(0,1, resolution, dtype=float),
                       np.linspace(0,30, resolution, dtype=float))
    X = np.array([x.flatten(), y.flatten()]).T
    z = F(X)
    fig = pyplot.figure()
    axe = fig.add_subplot(111,projection='3d')
    axe.plot_surface(x,y,z[:,0].reshape((resolution,resolution)),label="F")
    x0 = np.array([0.8,20])
    A = dF(x0)
    Y = A.dot((X - x0).T).T + F(x0[None,:])[0]
    axe.plot_surface(x,y,Y[:,0].reshape((resolution,resolution)),label="dF")

    pyplot.show()


if __name__ == '__main__':
    # latlong= np.array([[-75,43],[-10,0],[20,43] ])[:,(1,0)]
    # map_values(latlong,[0,1,2])
    aS = SubplotsSequence(2,2,3)
    for i , l in zip(range(10),aS):
        for a in l:
            a.plot([i] * 10)
    aS.show_first()
    pyplot.show()


