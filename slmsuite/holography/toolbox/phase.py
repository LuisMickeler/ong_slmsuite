"""
Repository of common analytic phase patterns.
"""
import os
import numpy as np
try:
    import cupy as cp   # type: ignore
except ImportError:
    cp = np
from scipy import special
from math import factorial
import matplotlib.pyplot as plt

from slmsuite.misc.math import REAL_TYPES
from slmsuite.holography.toolbox import _process_grid

# Load CUDA code. This is used for cupy.RawKernels in this file and elsewhere.

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cuda.cu"), 'r') as file:
    CUDA_KERNELS = file.read()

# Basic gratings.

def blaze(grid, vector=(0, 0)):
    r"""
    Returns a simple `blazed grating <https://en.wikipedia.org/wiki/Blazed_grating>`_,
    a linear phase ramp, toward a given vector in :math:`k`-space.

    .. math:: \phi(\vec{x}) = 2\pi \cdot \vec{k} \cdot \vec{x}

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        :math:`\vec{x}`. Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    vector : (float, float)
        :math:`\vec{k}`. Blaze vector in normalized :math:`\frac{k_x}{k}` units.
        See :meth:`~slmsuite.holography.toolbox.convert_vector()`

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)

    # Optimize phase construction based on context.
    if vector[0] == 0 and vector[1] == 0:
        result = np.zeros_like(x_grid)
    elif vector[1] == 0:
        result = (2 * np.pi * vector[0]) * x_grid
    elif vector[0] == 0:
        result = (2 * np.pi * vector[1]) * y_grid
    else:
        result = (2 * np.pi * vector[0]) * x_grid + (2 * np.pi * vector[1]) * y_grid

    return result


def sinusoid(grid, vector=(0, 0), shift=0, a=np.pi, b=0):
    r"""
    Returns a simple `holographic grating
    <https://en.wikipedia.org/wiki/Diffraction_grating#SR_(Surface_Relief)_gratings>`_,
    a sinusoidal grating, toward a given vector in :math:`k`-space.

    .. math:: \phi(\vec{x}) = \frac{a-b}{2} [1 + \cos(2\pi \cdot \vec{k} \cdot \vec{x} + s)] + b

    Important
    ---------
    Unlike a blazed grating :meth:`.blaze()`, power will efficiently be deflected toward
    the mirror -1st order at :math:`-\vec{k}`, by symmetry.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        :math:`\vec{x}`. Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    vector : (float, float)
        :math:`\vec{k}`. Blaze vector in normalized :math:`\frac{k_x}{k}` units.
        See :meth:`~slmsuite.holography.toolbox.convert_vector()`
    shift : float
        Radians to laterally shift the period of the grating by.
    a : float
        Value at one extreme of the sinusoid.
        Ignoring crosstalk,
        the 0th order will be minimized when ``|a-b|`` is equal to :math:`\pi`.
    b : float
        Value at the other extreme of the sinusoid.
        Defaults to zero, in which case ``a`` is the amplitude.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    if vector[0] == 0 and vector[1] == 0:
        (x_grid, _) = _process_grid(grid)
        result = np.full_like(x_grid, (a-b)/2 * (1 + np.sin(shift)))
    else:
        result = (a-b)/2 * (1 + np.sin(blaze(grid, vector) + shift))

    # Add offset if provided.
    if b != 0:
        result += b

    return result


def binary(grid, vector=(0, 0), shift=0, a=np.pi, b=0, duty_cycle=.5):
    r"""
    Returns a simple binary grating toward a given vector in :math:`k`-space.

    .. math:: \phi(\vec{x}) =
        \left\{
            \begin{array}{ll}
                a, & (
                    [2\pi \cdot \vec{k} \cdot \vec{x} + s] \,\,\,\,\text{mod}\,\,\,\, 2\pi
                    ) < 2\pi*d \\
                b, & \text{ otherwise}.
            \end{array}
        \right.

    Note
    ----
    When parameters are chosen to produce integer period,
    this function uses speed optimizations **(implementation incomplete)**.
    Otherwise, this function uses ``np.mod`` on top of
    :meth:`~slmsuite.holography.toolbox.phase.blaze()` to compute gratings.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        :math:`\vec{x}`. Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    vector : (float, float)
        :math:`\vec{k}`. Blaze vector in normalized :math:`\frac{k_x}{k}` units.
        See :meth:`~slmsuite.holography.toolbox.convert_vector()`
    shift : float
        Radians to laterally shift the period of the grating by.
    a : float
        Value at one extreme of the binary grating.
    b : float
        Value at the other extreme of the binary grating.
        Defaults to zero, in which case ``a`` is the amplitude.
    duty_cycle : float
        Ratio of the period which is 'on'.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    result = None

    if vector[0] == 0 and vector[1] == 0:
        (x_grid, _) = _process_grid(grid)
        phase = b
        if shift != 0:
            if np.mod(shift, 2*np.pi) < (2 * np.pi * duty_cycle):
                phase = a
        result = np.full(x_grid.shape, phase)
    elif vector[0] != 0 and vector[1] != 0:
        pass    # xor the next case.
    elif vector[0] == 0 or vector[1] == 0:
        period = 1/np.sum(vector)
        duty = period*duty_cycle

        period_int = np.rint(period)
        duty_int = np.rint(duty)

        if np.all(np.isclose(period, period_int)) and np.all(np.isclose(duty, duty_int)):
            pass    # Future: speed optimization.

    # If we have not set result, then we have to use the slow np.mod option.
    if result is None:
        result = np.where(
            np.mod(blaze(grid, vector, shift), 2*np.pi) < (2 * np.pi * duty_cycle),
            b,
            a,
        )

    return result


# Basic lenses.

def _parse_focal_length(f):
    """Helper function to parse focal length used by `lens` and `axicon`."""
    if isinstance(f, REAL_TYPES):
        f = [f, f]
    if isinstance(f, (list, tuple, np.ndarray)):
        f = np.squeeze(f)

        if f.size != 2:
            raise ValueError("Expected two terms in focal list. Found {}.".format(f))
        if np.any(f == 0):
            raise ValueError("Cannot interpret a focal length of zero. Found {}.".format(f))

    return f


def lens(grid, f=(np.inf, np.inf)):
    r"""
    Returns a simple
    `thin parabolic lens <https://en.wikipedia.org/wiki/Thin_lens#Physical_optics>`_.

    When the focal length :math:`f` is isotropic,

    .. math:: \phi(\vec{x}) = \frac{\pi}{f}|\vec{x}|^2

    Otherwise :math:`\vec{\,f\,}` represents an elliptical lens,

    .. math:: \phi(x, y) = \pi \left[\frac{x^2}{f_x} + \frac{y^2}{f_y} \right]

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    f : float OR (float, float)
        Focus in normalized :math:`\frac{x}{\lambda}` units.
        Defaults to infinity (no lens).
        Scalars are interpreted as a non-cylindrical isotropic lens.
        Future: add a ``convert_focal_length`` method to parallel
        :meth:`.convert_vector()`. TODO: see depth conversion.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)
    f = _parse_focal_length(f)

    # Optimize phase construction based on context (for speed, to avoid square, etc).
    if np.isfinite(f[0]) and np.isfinite(f[1]):
        return (np.pi / f[0]) * np.square(x_grid) + (np.pi / f[1]) * np.square(y_grid)
    elif np.isfinite(f[0]) and np.isfinite(f[1]):
        return (np.pi / f[0]) * np.square(x_grid)
    elif np.isfinite(f[1]):
        return (np.pi / f[1]) * np.square(y_grid)
    else:
        return np.zeros_like(x_grid)


def axicon(grid, f=(np.inf, np.inf), w=None):
    r"""
    Returns an `axicon <https://en.wikipedia.org/wiki/Axicon>`_ lens,
    the phase farfield for a Bessel beam. A (elliptically)-cylindrical axicon blazes
    according to :math:`\vec{k}_g = w / \vec{\,f\,} / 2` where
    :math:`w` is the radius of the axicon. With a flat input amplitude over
    :math:`[-w, w]`, this will produce a Bessel beam focussed at :math:`z = \vec{f}`.

    .. math:: \phi(\vec{x}) = 2\pi \cdot |\vec{k}_g \cdot \vec{x}|

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    f : float OR (float, float)
        Focal length (center of the axicon diamond) in normalized :math:`\frac{x}{\lambda}` units.
        Scalars are interpreted as a non-cylindrical isotropic axicon.
        Defaults to infinity (no axicon).
    w : float OR None
        See :meth:`~slmsuite.holography.toolbox._determine_source_radius()`.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)
    w = _determine_source_radius(grid, w)
    f = _parse_focal_length(f)

    angle = [w / f[0] / 2, w / f[1] / 2]    # Notice that this fraction is in radians.

    # Optimize phase construction based on context (for speed, to avoid sqrt, etc).
    if angle[0] == 0 and angle[1] == 0:
        return 0 * x_grid
    elif angle[0] == 0:
        return (2 * np.pi * angle[1]) * np.abs(y_grid)
    elif angle[1] == 0:
        return (2 * np.pi * angle[0]) * np.abs(x_grid)
    else:
        return (2 * np.pi) * np.sqrt(np.square(x_grid * angle[0]) + np.square(y_grid * angle[1]))


# Zernike.

ZERNIKE_INDEXING_DIMENSION = {"ansi" : 1, "noll" : 1, "fringe" : 1, "wyant" : 1, "radial" : 2}
ZERNIKE_INDEXING = ZERNIKE_INDEXING_DIMENSION.keys()
ZERNIKE_NAMES = [
    # Oth order
    "Piston",

    # 1st order
    "Vertical tilt",
    "Horizontal tilt",

    # 2nd order
    "Oblique astigmatism",
    "Defocus",
    "Vertical astigmatism",

    # 3rd order
    "Vertical trefoil",
    "Vertical coma",
    "Horizontal coma",
    "Oblique trefoil",

    # 4th order
    "Oblique quadrafoil",
    "Oblique secondary astigmatism",
    "Spherical aberration",
    "Vertical secondary astigmatism",
    "Vertical quadrafoil",

    # 5th order
    "Vertical pentafoil",
    "Vertical secondary trefoil",
    "Vertical secondary coma",
    "Horizontal secondary coma",
    "Oblique secondary trefoil",
    "Oblique pentafoil",

    # 6th order
    "Oblique hexafoil",
    "Oblique secondary quadrafoil",
    "Oblique trinary astigmatism",
    "Secondary spherical aberration",
    "Vertical trinary astigmatism",
    "Vertical secondary quadrafoil",
    "Vertical hexafoil",
]


def zernike_convert_index(indices, from_index="ansi", to_index="ansi"):
    """
    Helper function for converting between Zernike indexing conventions.

    Currently supported conventions:

    -  ``"radial"``
        The standard 2-dimensional :math:`n,l` indexing for
        `Zernike polynomials <https://en.wikipedia.org/wiki/Zernike_polynomials>`_,
        where :math:`n` is the radial index
        and :math:`l` is the azimuthal index.
        Denoted :math:`Z_n^l`.

    -  ``"ansi"``
        1-dimensional (0-indexed) `ANSI indices
        <https://en.wikipedia.org/wiki/Zernike_polynomials#OSA/ANSI_standard_indices>`_.
        **This is the default** :mod:`slmsuite` **index.**
        Denoted :math:`Z_i`.

    -  ``"noll"``
        1-dimensional (1-indexed) `Noll indices
        <https://en.wikipedia.org/wiki/Zernike_polynomials#Noll's_sequential_indices>`_.

    -  ``"fringe"``
        1-dimensional (1-indexed) `Fringe indices
        <https://en.wikipedia.org/wiki/Zernike_polynomials#Fringe/University_of_Arizona_indices>`_.

    -  ``"wyant"``
        1-dimensional (0-indexed) `Wyant indices
        <https://en.wikipedia.org/wiki/Zernike_polynomials#Wyant_indices>`_.
        Equivalent to ``"fringe"``, except with starting with zero instead of one.

    Parameters
    ----------
    indices : array_like
        List of indices of shape ``(N, D)`` where ``D`` is the dimension of the indexing
        (1, apart from ``"radial"`` indexing which has a dimension of 2).
    from_index, to_index : str
        Zernike index convention. Must be supported.

    Returns
    -------
    indices_converted : numpy.ndarray
        List of indices of shape ``(N, D)`` where ``D`` is the dimension of the indexing
        (1, apart from ``"radial"`` indexing which has a dimension of 2).

    Raises
    ------
    ValueError
        If an invalid index number or index type is given,
        or an invalid indices shape is given.
    """
    # Parse arguments.
    if from_index not in ZERNIKE_INDEXING:
        raise ValueError(
            f"From index '{from_index}' not recognized as a valid unit. "
            f"Options: {ZERNIKE_INDEXING}."
        )
    if to_index not in ZERNIKE_INDEXING:
        raise ValueError(
            f"To index '{to_index}' not recognized as a valid unit. "
            f"Options: {ZERNIKE_INDEXING}."
        )

    dimension = ZERNIKE_INDEXING_DIMENSION[from_index]

    indices = np.array(indices, dtype=int, copy=None)
    if indices.size == dimension:
        indices = indices.reshape((1, dimension))
    if dimension > 1 and indices.shape[1] != dimension:
        raise ValueError(f"Expected dimension (N, {dimension}); found {indices.shape}")

    if from_index == to_index:
        return indices

    # Convert all cases to radial indices n, l.
    if from_index == "radial":
        n = indices[:,0]
        l = indices[:,1]
    elif from_index == "noll" or to_index == "fringe" or from_index == "wyant":
        # Inverse functions have not been implemented.
        raise NotImplementedError(f"from_index '{from_index}' is not supported currently.")
    elif from_index == "ansi":
        n = np.floor(.5 * np.sqrt(8*indices + 1) - .5).astype(int)
        l = 2*indices - n*(n+2)

    # Error check n,l
    if np.any((n + l) % 2):
        raise ValueError(f"Invalid Zernike index n,l. n+l must be even. n={n}, l={l}.")
    if np.any(np.abs(l) > n):
        raise ValueError(f"Invalid Zernike index n,l. |l| cannot be larger than n. n={n}, l={l}.")
    if np.any(n < 0):
        raise ValueError(f"Invalid Zernike index n,l. n must be non-negative. n={n}, l={l}.")

    # Convert to the desired indices.
    if to_index == "radial":
        result = np.vstack((n, l)).T
    elif to_index == "noll":
        result = (n * (n + 1)) // 2 + np.abs(l)
        result += np.logical_and(l >= 0, np.mod(n, 4) <= 1)
        result += np.logical_and(l <= 0, np.mod(n, 4) > 1)
    elif to_index == "wyant" or to_index == "fringe":
        result = (
            np.square(1 + (n + np.abs(l)) / 2).astype(int)
            - 2 * np.abs(l) + (l < 0)
            - (to_index == "wyant")
        )
    elif to_index == "ansi":
        result = (n * (n + 2) + l) // 2

    return result


def zernike_aperture(grid, aperture=None):
    """
    Helper function to find the appropriate scaling for between the normalized units in
    the grid and the Zernike aperture (the unit disk).

    Important
    ~~~~~~~~~
    Zernike polynomials are canonically defined on a circular aperture. However, we may
    want to use these polynomials on other apertures (e.g. a rectangular SLM).
    Cropping this aperture breaks the orthogonality and normalization of the set, but
    this is fine for many applications. While it is possible to orthonormalize the
    cropped set, we do not do so in :mod:`slmsuite`, as this is not critical for target
    applications such as aberration correction.

    Caution
    ~~~~~~~
    Anisotropic Zernike scaling can lead to unexpected behavior.
    For instance, the :math:`Z_4 = Z_2^0 = 1 - 2x^2 - 2y^2` Zernike term is commonly
    used for focusing, but with anisotropic scaling, this becomes an elliptical lens
    on the SLM which may not behave as expected.

    Parameters
    ----------
    aperture : {"circular", "elliptical", "cropped"} OR (float, float) OR float OR None
        How to scale the polynomials relative to the grid shape. This is relative
        to the :math:`R = 1` edge of a standard Zernike pupil.

        - ``None``
          If a :class:`~slmsuite.hardware.slms.slm.SLM` is passed for ``grid``, then
          uses :meth:`~slmsuite.hardware.slms.slm.SLM.get_source_zernike_scaling()` to
          determine the scaling most appropriate for the SLM.
          Otherwise, defaults to ``"cropped"``.
          See also :meth:`~slmsuite.hardware.slms.slm.SLM.fit_source_amplitude()`
          and especially the `extent_threshold` keyword which determines the scaling used by
          :meth:`~slmsuite.hardware.slms.slm.SLM.get_source_zernike_scaling()`

        - ``"circular"``
          The circle is scaled isotropically until the pupil edge touches one set
          of opposite grid edges. This is the default aperture.

        - ``"elliptical"``
          The circle is scaled anisotropically until each pupil edge touches a grid
          edge. Generally produces an ellipse.

        - ``"cropped"``
          The circle is scaled isotropically until the rectangle of the grid is
          circumscribed by the circle.

        - ``float OR (float, float)``
          Custom scaling. These values are multiplied to the ``x_grid`` and ``y_grid``
          directly, respectively. The edge of the Zernike pupil corresponds to where
          ``(s_x * x_grid)**2 + (s_y * y_grid)**2 = 1``. If a scalar is given, assumes
          isotropic scaling.

    Returns
    ~~~~~~~
    (float, float)
    """
    # Parse grid.
    (x_grid, y_grid) = _process_grid(grid)

    # Parse aperture.
    if aperture is None:
        # Check if cameraslm.
        if hasattr(grid, "slm"):
            grid = grid.slm

        # Check if slm.
        if hasattr(grid, "get_source_zernike_scaling"):
            aperture = grid.get_source_zernike_scaling()
        else:
            aperture = "cropped"

    if isinstance(aperture, str):
        if aperture == "elliptical":
            x_scale = 1 / np.nanmax(x_grid)
            y_scale = 1 / np.nanmax(y_grid)
        elif aperture == "circular":
            x_scale = y_scale = 1 / np.amin([np.nanmax(x_grid), np.nanmax(y_grid)])
        elif aperture == "cropped":
            x_scale = y_scale = 1 / np.sqrt(np.nanmax(np.square(x_grid) + np.square(y_grid)))
        else:
            raise ValueError("NotImplemented")
    elif np.isscalar(aperture):
        x_scale = y_scale = aperture
    elif isinstance(aperture, (list, tuple, np.ndarray)) and len(aperture) == 2:
        x_scale = aperture[0]
        y_scale = aperture[1]
    else:
        raise ValueError("Aperture type {} not recognized.".format(type(aperture)))

    return (x_scale, y_scale)


def zernike(grid, index, weight=1, **kwargs):
    r"""
    Returns a single real `Zernike polynomial <https://en.wikipedia.org/wiki/Zernike_polynomials>`_.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    index : int
        ANSI Zernike index defining the polynomial.
    weight : float
        Amplitude of the polynomial.
    **kwargs
        Passed to :meth:`.zernike_sum()`.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    return zernike_sum(grid, (int(index),), (float(weight),), **kwargs)


def zernike_sum(grid, indices, weights, aperture=None, use_mask=True, derivative=(0,0), out=None):
    r"""
    Returns a summation of
    `Zernike polynomials <https://en.wikipedia.org/wiki/Zernike_polynomials>`_
    in a computationally-efficient manner. Specifically,

    .. math:: \phi(\vec{x}) = \sum_i w_i Z_{I_i}(\vec{x}).

    To improve performance, especially for higher order polynomials,
    we store a cache of Zernike coefficients to avoid regeneration.
    See the below example to generate
    :math:`Z_1 - Z_2 + Z_4 = Z_1^{-1} - Z_1^1 + Z_2^0`,
    where the standard radial Zernike indexing :math:`Z_n^l`
    is instead represented as :math:`Z_i` by the 1-dimensional ANSI index :math:`i`.

    .. highlight:: python
    .. code-block:: python

        zernike_sum_phase = toolbox.phase.zernike_sum(
            grid=slm,
            indices=(1,  2,  4),    # Define Z_1, Z_2, Z_4
            weights=(1, -1,  1),    # Request Z_1 - Z_2 + Z_4
            aperture="circular"
        )

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    indices : array_like of int
        Which Zernike polynomials to sum, defined by ANSI indices. Of shape ``(D,)``.

        Tip
        ~~~
        Use :meth:`~slmsuite.holography.toolbox.phase.zernike_convert_index()`
        to convert to ANSI from various other common indexing conventions.

    weights : array_like of float
        The weight for each given index. Of shape ``(D,)``.
        If a stack of zernike sums is desired, then use shape ``(D, N)``.
    aperture : {"circular", "elliptical", "cropped"} OR (float, float) OR float OR None
        Determines how the Zernike polynomials are laterally scaled.
        Parsed with :meth:`~slmsuite.holography.toolbox.phase.zernike_aperture()`.

        Important
        ~~~~~~~~~
        Read the documentation and tips in
        :meth:`~slmsuite.holography.toolbox.phase.zernike_aperture()`
        to avoid subtle issues with lateral scaling.

    use_mask : bool OR "return"
        If ``True``, sets the area where standard Zernike polynomials are undefined to zero.
        If ``False``, the polynomial is not cropped. This should be used carefully, as
        the wavefront correction outside the unit circle quickly explodes with
        :math:`r^O` for terms of high order :math:`O`.
        If ``"return"``, returns the 2D mask ``x_grid**2 + y_grid**2 <= 1``.
    derivative : (int, int)
        If non-negative, returns the Zernike derivative of the given order. For instance,
        ``(1, 0)`` corresponds to the first derivative in the :math:`x` direction.
        This is fast and accurate because the derivative is computed via power rule before
        generating Zernike images.
    out : array_like OR None
        Memory to be used for the phase output. Allocated separately if ``None``.

    Returns
    -------
    numpy.ndarray
        The phase for this function. Optionally returns the 2D Zernike mask.
    """
    # Parse passed simple values.
    (x_grid, y_grid) = _process_grid(grid)
    (x_scale, y_scale) = zernike_aperture(grid, aperture)
    if len(derivative) != 2:
        raise ValueError("Expected derivative to be a (int, int)")

    # Parse indices.
    indices = np.squeeze(indices)
    if indices.ndim == 0:
        indices = np.array([indices])
    elif indices.ndim > 1:
        raise ValueError("indices should be a 1D vector.")
    D = len(indices)

    # Parse weights.
    weights = np.squeeze(weights)
    if weights.ndim <= 1:
        if weights.ndim == 0:
            weights = np.array([weights])

        if len(weights) == D:
            weights = np.reshape(weights, (-1, 1))
        else:
            raise ValueError("Expected weights to have a common dimension with indices.")
    elif weights.ndim == 2:
        if weights.shape[0] != D:
            raise ValueError("Expected weights to have a common dimension with indices.")
    else:
        raise ValueError("Expected weights to be 1D or 2D.")

    (D, N) = weights.shape

    # Parse out.
    out = _parse_out(x_grid, out, stack=N)

    # At the end, we're going to set the values outside the aperture to zero.
    # Make a mask for this if it's necessary.
    if use_mask is False:
        mask = None
    else:
        mask = np.square(x_grid * x_scale) + np.square(y_grid * y_scale) <= 1
        if use_mask == "return":
            return mask
        use_mask = use_mask and np.any(mask == 0)

    # Make the new grids.
    if use_mask:
        x_grid_scaled = x_grid[mask] * x_scale
        y_grid_scaled = y_grid[mask] * y_scale
    else:
        # Special case to avoid copying grids in the case of no scaling.
        if x_scale == 1:    x_grid_scaled = x_grid
        else:               x_grid_scaled = x_grid * x_scale
        if y_scale == 1:    y_grid_scaled = y_grid
        else:               y_grid_scaled = y_grid * y_scale

    _zernike_build_indices(indices)
    zernike_cantor = _zernike_cache_vectorized[indices, :]   # (D, M)
    M = zernike_cantor.shape[1]
    cantor_indices = np.arange(M)

    # Remove terms with all zeros
    nonzero = np.any(zernike_cantor, axis=0)    # Which D are nonzero for given m in M
    cantor_indices = cantor_indices[nonzero]    # M -> M'
    zernike_cantor = zernike_cantor[:, nonzero]

    # Differentiate the terms if needed.
    if np.any(derivative):
        cantor_pairing = _inverse_cantor_pairing(cantor_indices)    # (M', 2)

        for j in [0, 1]:
            if derivative[j] > 0:
                power = cantor_pairing[:, [j]].T.astype(int)  # (D, 1)

                # Apply the power rule.
                if derivative[j] == 1:
                    zernike_cantor *= power
                elif derivative[j] > 1:
                    nonzero = power > derivative[j]

                    zernike_cantor[np.logical_not(nonzero)] = 0
                    zernike_cantor[nonzero] *= (
                        special.factorial(power[nonzero]) / special.factorial(power[nonzero] - derivative[j])
                    ).astype(int)

                # Reduce the power of the term
                reduced = cantor_pairing[:, j] > 0
                cantor_pairing[reduced, j] -= derivative[j]
                cantor_pairing[np.logical_and(reduced, cantor_pairing[:, j] < 0), j] = 0

        # Remove terms with all zeros
        nonzero = np.any(zernike_cantor, axis=0)        # Which D are nonzero for given m in M'
        cantor_pairing = cantor_pairing[nonzero, :]     # M' -> M''
        zernike_cantor = zernike_cantor[:, nonzero]

        terms = cantor_pairing
    else:
        terms = cantor_indices

    # Reshape the weights into this new basis.
    cantor_weights = np.matmul(zernike_cantor.T, weights)  # (M', D) x (D, N) = (M', N)

    # The masked case only computes on a fraction of the full space.
    if use_mask:
        out[:, mask] = polynomial(
            grid=(x_grid_scaled, y_grid_scaled),
            weights=cantor_weights,
            terms=terms,
            out=out[:, mask]
        )
    else:
        out = polynomial(
            grid=(x_grid_scaled, y_grid_scaled),
            weights=cantor_weights,
            terms=terms,
            out=out
        )

    if N == 1:
        return out.reshape(x_grid.shape)
    else:
        return out


def _plot_zernike_pyramid(grid, order, scale=1, **kwargs):
    r"""
    Plots :meth:`.zernike()` on a pyramid of subplots corresponding to the radial and
    azimuthal order. The user can resize the figure with ``plt.figure()`` beforehand
    and force ``plt.show()`` afterward.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    order : int
        Maximum radial order to plot.
    scale : float
        Scales the subplots to ``[-scale, scale]``.
    **kwargs
        Passed to :meth:`.zernike()`.
    """
    order = int(order + 1)
    indices_ansi = np.arange((order * (order + 1)) // 2)
    indices_radial = zernike_convert_index(indices_ansi, from_index="ansi", to_index="radial")

    # Get the pitch of the subplots for later.
    a1 = plt.subplot(order, order, 1)
    a2 = plt.subplot(order, order, 2)

    pitch = a2.get_position().xmin - a1.get_position().xmin

    a1.remove()
    a2.remove()

    for i in indices_ansi:
        n, l = indices_radial[i, :]
        m = (n + l) // 2

        phase = zernike(grid, i, 1, **kwargs)

        a = plt.subplot(order, order, 1 + m + n*order)
        # plt.title((n,l))
        if i < len(ZERNIKE_NAMES):
            plt.title(f"#{i}\n({n}, {l})\n" + ZERNIKE_NAMES[i])
        else:
            plt.title(i)
        plt.imshow(phase, cmap="twilight")
        plt.clim([-scale, scale])
        plt.xticks([])
        plt.yticks([])

        dx = .5 * (3*order - n)
        box = a.get_position()
        box = box.translated(dx * pitch, 0)
        a.set_position(box)


# Old style dictionary.     {(n,m) : {(nx, ny) : w, ... }, ... }
_zernike_cache = {}

# New style matrix.         N x M, N: ANSI Zernike, M: cantor polynomial.
_zernike_cache_vectorized = np.array([[]], dtype=int)


def _zernike_build_order(o):
    """Pre-caches Zernike polynomial coefficients up to order :math:`n`."""
    N = (n+1) * (n+2) // 2
    for i in range(N):
        _zernike_coefficients(i)

def _zernike_build_indices(indices):
    """Pre-caches Zernike polynomial coefficients up to order :math:`n`."""
    for i in indices:
        _zernike_coefficients(i)


def _zernike_coefficients(index):
    """
    Returns the coefficients for the :math:`x^ay^b` terms of the real Zernike polynomial
    of ANSI index ``i``. This is returned as a dictionary of form ``{(a,b) : coefficient}``.
    Uses `this algorithm <https://doi.org/10.1117/12.294412>`_.
    """
    index = int(index)

    # Generate coefficients only if we have not already generated.
    if not index in _zernike_cache:
        zernike_this = {}

        (n, l) = zernike_convert_index(index, to_index="radial")[0]
        l = -l

        # Define helper variables.
        if l % 2:   # If even
            q = int((abs(l) - 1) / 2)
        else:
            if l > 0:
                q = int(abs(l)/2 - 1)
            else:
                q = int(abs(l)/2)

        if l <= 0:
            p = 0
        else:
            p = 1

        l = abs(l)
        m = int((n-l)/2)

        # Helper function
        def comb(n, k):
            return factorial(n) / (factorial(k) * factorial(n-k))

        # Finding the coefficients is a summed combinatorial search.
        # This is why we cache: so we don't have to do this many times,
        # especially for higher order polynomials and the corresponding cubic scaling.
        for i in range(q+1):
            for j in range(m+1):
                for k in range(m-j+1):
                    factor = -1 if (i + j) % 2 else 1
                    factor *= comb(l, 2 * i + p)
                    factor *= comb(m - j, k)
                    factor *= (
                        float(factorial(n - j))
                        / (factorial(j) * factorial(m - j) * factorial(n - m - j))
                    )

                    power_key = (int(n - 2*(i + j + k) - p), int(2 * (i + k) + p))

                    # Add this coefficient to the element in the dictionary
                    # corresponding to the right power.
                    if power_key in zernike_this:
                        zernike_this[power_key] += int(factor)
                    else:
                        zernike_this[power_key] = int(factor)

        # Update the cache. Remove all factors that have cancelled out (== 0).
        _zernike_cache[index] = {
            power_key: factor
            for power_key, factor in zernike_this.items()
            if factor != 0
        }

        # If we need to, enlarge the vector cache.
        N = (n+1) * (n+2) // 2      # The Zernike order determines the size of the cache.
        global _zernike_cache_vectorized

        if _zernike_cache_vectorized.shape[1] < N:
            _zernike_cache_vectorized = np.pad(
                _zernike_cache_vectorized,
                (
                    (0, N - _zernike_cache_vectorized.shape[0]),
                    (0, N - _zernike_cache_vectorized.shape[1])
                ),
                constant_values=0
            )

        # Update the vectorized dict.
        for power_key, factor in _zernike_cache[index].items():
            cantor_index = _cantor_pairing(power_key)
            _zernike_cache_vectorized[index, cantor_index] = factor

    return _zernike_cache[index]


def _zernike2cantor(indices, coefficients):
    pass


def _zernike_populate_basis_map(indices):
    """
    This generates helper maps ``c_md``, ``i_md``, ``pxy_m`` for use in GPU kernels
    (see ``populate_basis`` in cuda.cu).
    """
    indices = np.squeeze(indices)
    D = len(indices)

    # Omit negative indices (special cases)
    zernike_indices = indices[indices >= 0]
    other_indices = indices[indices < 0]

    # Make sure all coefficients are generated.
    for i in zernike_indices:
        _zernike_coefficients(i)

    # Determine the cantor indices.
    nonzero_cantor_indices = np.any(_zernike_cache_vectorized[zernike_indices, :], axis=0)
    cantor_indices = np.arange(len(nonzero_cantor_indices), dtype=int)[nonzero_cantor_indices]

    M = len(cantor_indices)

    pxy_m = _inverse_cantor_pairing(cantor_indices)

    # Find an optimal sort pattern for constructing the polynomials.
    # msort = _term_pathing(pxy_m)
    msort = np.arange(M)
    pxy_m = pxy_m[msort, :].astype(int)

    # Reinsert the other cases.
    if len(other_indices) > 0:
        pxy_m = np.pad(pxy_m, ((0, len(other_indices)), (0,0)))
        pxy_m[len(zernike_indices):, 0] = other_indices     # Other indices go into nx.

    # Populate the results.
    c_md = _zernike_cache_vectorized[zernike_indices, :][:, cantor_indices[msort]].T.astype(np.float32)
    i_md = np.full((M, D), -1, dtype=int)

    darange = np.arange(len(zernike_indices))

    for m in msort:
        nonzero = darange[c_md[m, :] != 0]
        i_md[m, :len(nonzero)] = nonzero

    return c_md, i_md, pxy_m.T


try:
    _zernike_test_kernel = cp.RawKernel(CUDA_KERNELS, 'zernike_test')
except:
    _zernike_test_kernel = None


def _zernike_test(grid, indices):
    c_md, i_md, pxy_m = _zernike_populate_basis_map(indices)

    # Parse grid.
    (x_grid, y_grid) = _process_grid(grid)
    scale = 1
    if hasattr(grid, "get_source_zernike_scaling"):
        scale = grid.get_source_zernike_scaling()
    x_grid = cp.array(x_grid.astype(np.float32) * scale, copy=None)
    y_grid = cp.array(y_grid.astype(np.float32) * scale, copy=None)

    (H, W) = x_grid.shape
    WH = int(W*H)
    (M, D) = c_md.shape

    out = cp.empty((D,H,W), dtype=np.float32)

    threads_per_block = int(_zernike_test_kernel.max_threads_per_block)
    blocks = WH // threads_per_block

    # Call the RawKernel.
    _zernike_test_kernel(
        (blocks,),
        (threads_per_block,),
        (
            WH, D, M,
            cp.array(c_md.ravel(), copy=None),
            cp.array(i_md.ravel(), copy=None),
            cp.array(pxy_m.ravel(), copy=None),
            x_grid.ravel(),
            y_grid.ravel(),
            out.ravel()
        )
    )

    return out


# Polynomials.

def _cantor_pairing(xy):
    """
    Converts a 2D index to a unique 1D index according to the
    `Cantor pairing function <https://en.wikipedia.org/wiki/Pairing_function>`.
    """
    xy = np.array(xy, dtype=int, copy=None).reshape((-1, 2))
    return np.rint(.5 * (xy[:,0] + xy[:,1]) * (xy[:,0] + xy[:,1] + 1) + xy[:,1]).astype(int)


def _inverse_cantor_pairing(z):
    """
    Converts a 1D index to a unique 2D index according to the
    `Cantor pairing function <https://en.wikipedia.org/wiki/Pairing_function>`.

    Returns shape ``(D, 2)``
    """
    z = np.array(z, dtype=int, copy=None)
    if z.ndim != 1:
        raise ValueError("Expected a list of shape (D,)")

    w = np.floor((np.sqrt(8*z + 1) - 1) // 2).astype(int)
    t = (w*w + w) // 2

    y = z-t
    x = w-y

    # Handle negative index case which is used for special indices.
    y[z < 0] = 0
    x[z < 0] = z[z < 0]

    return np.vstack((x, y)).T


def _term_pathing(xy):
    """
    Returns the index for term sorting to minimize number of monomial multiplications when summing
    polynomials (with only one storage variable).

    It may be the case that division could yield a shorter path, but division is
    generally more expensive than multiplication so we omit this scenario.

    It may also be the case that optimizing for large-step multiplications can yield a
    speedup. (e.g. `x^5 = y * y * x` with `y = x * x` costs three multiplications instead
    of five) However, it is unlikely that users will need the very-high-order
    polynomials would would experience an appreciable speedup.

    Parameters
    ----------
    xy : array_like
        Array of shape ``(M, 2)``.

    Returns
    -------
    I : numpy.ndarray
        Array of shape ``(M,)``. Best coefficient order.
    """
    # Prepare helper variables.
    xy = np.array(xy, dtype=int, copy=None)

    order = np.sum(xy, axis=1)
    delta = np.squeeze(np.diff(xy, axis=1))

    cantor = _cantor_pairing(xy)
    cantor_index = np.argsort(-cantor)

    # Prepare the output data structure.
    I = np.zeros_like(order, dtype=int)

    # Helper function to recurse through pathing options.
    def recurse(i0, j0):
        # Fill in the current values.
        I[j0] = cantor_index[i0]
        cantor[cantor_index[i0]] = -1

        if j0 == 0:
            return 0

        # Figure out the distance between the current index and all other indices.
        dd = delta - delta[cantor_index[i0]]
        do = order[cantor_index[i0]] - order

        # Find the best candidate for the next index in the thread.
        nearest = -cantor + np.where((np.abs(dd) > do) + (do <= 0) + (cantor < 0), np.inf, 0)
        i = np.argmin(nearest[cantor_index])

        # Either exit or continue this thread.
        if cantor[cantor_index[i]] != -1:
            return recurse(i, j0-1)
        else:
            return j0-1

    # Traverse backwards through the array,
    j = len(I)-1
    for i in range(len(order)):
        if cantor[cantor_index[i]] >= 0 and j >= 0:
            j = recurse(i, j)

    return I


def _parse_out(x_grid, out, stack=1):
    """
    Helper function to error check the shape and type of ``out``.
    """
    shape = tuple(np.concatenate(([stack], x_grid.shape)))

    if out is None:
        # Initialize out to zero.
        if cp == np:
            out = np.zeros(shape, x_grid.dtype)
        else:
            out = cp.get_array_module(x_grid).zeros(shape, x_grid.dtype)

        return out
    else:
        # Error check user-provided out.
        if out.size != np.prod(shape):
            raise ValueError("out must have same size as the stacked grid.")
        if out.dtype != x_grid.dtype:
            raise ValueError("out must have same type as grid.")
        if cp != np and cp.get_array_module(x_grid) != cp.get_array_module(out):
            raise ValueError("out and grid must both be cupy arrays if one is.")

        return out.reshape(shape)


def polynomial(grid, weights, terms=None, pathing=None, out=None):
    r"""
    Returns a summation of monomials. Specifically,

    .. math:: \phi(x, y) = \sum_{n,m \in T} w_{nm}x^ny^m

    where :math:`w_{nm}` are floating-point weights.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    weights : array_like of float
        Array of shape ``(D,)`` corresponding to the coefficient of each term.
        Can also be shape ``(D, N)`` if a stack of ``N`` polynomials is desired.
    terms : array_like of int OR None
        Array of shape ``(D, 2)`` corresponding to the :math:`x` and :math:`y` exponents
        for the ``D`` terms.
        Otherwise, array of shape ``(D,)`` corresponding to the Cantor indices of
        monomials.
        If ``None``, assumes the terms are Cantor indices of the range of ``weights``.
    pathing : array_like of int OR None
        Array of shape ``(D,)`` corresponding to an order that the terms should be
        calculated. If ``None``, chooses the path that reduces the number of
        multiplications when evaluating monomials.
    out : numpy.ndarray OR cupy.ndarray
        A location where the result is stored. Use this to avoid allocating new memory.

    Returns
    -------
    out : numpy.ndarray OR cupy.ndarray
        Result of the sum.
    """
    # Parse terms
    terms = np.array(terms)
    if terms is None:
        terms = _inverse_cantor_pairing(np.arange(D))

    if terms.ndim == 1:
        terms = _inverse_cantor_pairing(terms)

    if terms.shape[1] != 2:
        raise ValueError("Terms must be of shape (D, 2) or (D,). Found {}.".format(terms.shape))

    D = terms.shape[0]

    # Parse weights
    weights = np.array(weights)
    if weights.ndim == 1:
        if len(weights) == D:
            weights = np.reshape(weights, (-1, 1))
        else:
            raise ValueError("Expected weights to have a common dimension with indices.")
    elif weights.ndim == 2:
        if weights.shape[0] != D:
            raise ValueError("Expected weights to have a common dimension with indices.")
    else:
        raise ValueError("Expected weights to be 1D or 2D.")

    (D, N) = weights.shape

    # Parse pathing
    if pathing is False:
        pathing = np.arange(terms.shape[0])
    if pathing is None:
        pathing = _term_pathing(terms)

    # Prepare the grids and canvas.
    (x_grid, y_grid) = _process_grid(grid)
    out = _parse_out(x_grid, out, stack=N)

    out.fill(0)
    nx0 = ny0 = 0
    if cp == np:
        monomial = np.ones_like(x_grid)
    else:
        monomial = cp.get_array_module(x_grid).ones_like(x_grid)

    # Force datatype for easier multiplication.
    weights = weights.astype(out.dtype)

    # Sum the result.
    for index in pathing:
        (nx, ny) = terms[index, :]

        if nx >= 0:                     # Usual case: monomial.
            # Reset if we're starting a new path.
            if nx - nx0 < 0 or ny - ny0 < 0:
                nx0 = ny0 = 0
                monomial.fill(1)

            # Traverse the path in +x or +y.
            for _ in range(nx - nx0):
                monomial *= x_grid
            for _ in range(ny - ny0):
                monomial *= y_grid

            # Update the current index.
            nx0, ny0 = nx, ny

            # We use a for loop here because the arrays will already be big (vectorization
            # overhead already amortized) and multiplying with zero or special indexing
            # can cost, esp. on GPU and scalar transfer is easier.
            for i in range(N):
                if weights[index, i] != 0:
                    out[i, ...] += weights[index, i] * monomial
        elif nx == -1 and ny == 0:      # Special case: vortex waveplate.
            lg = np.arctan2(y_grid, x_grid)

            for i in range(N):
                if weights[index, i] > 0:
                    out[i, ...] += weights[index, i] * lg
        else:
            raise ValueError("Unrecognized")

    return out


# Structured light.

def _determine_source_radius(grid, w=None):
    r"""
    Helper function to determine the assumed Gaussian source :math:`1/e` amplitude
    radius (:math:`1/e^2` power radius) for various
    structured light conversion functions. This is important because structured light
    conversions need knowledge of the size of the incident Gaussian beam.
    For example, see the ``w`` parameter in
    :meth:`~slmsuite.holography.toolbox.phase.laguerre_gaussian()`.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    w : float OR None
        The radius of the phase pattern in normalized :math:`\frac{x}{\lambda}` units.
        To produce perfect structured beams, this radius is equal to the radius of
        the gaussian profile of the source (ideally not clipped by the SLM).
        If an SLM was passed as grid, retrieves the data from
        :attr:`slmsuite.hardware.slms.slm.SLM.source` and
        :meth:`slmsuite.hardware.slms.slm.SLM.fit_source_amplitude()`.
        If ``w`` is left as ``None``, ``w`` is set to a quarter of the smallest normalized screen dimension.

    Returns
    -------
    w : float
        Determined radius. In normalized units.
    """
    if w is not None:
        return w

    if hasattr(grid, "slm"):
        grid = grid.slm
    if hasattr(grid, "get_source_radius"):
        return grid.get_source_radius()

    (x_grid, y_grid) = _process_grid(grid)
    return np.min([np.amax(x_grid), np.amax(y_grid)]) / 4


def laguerre_gaussian(grid, l, p, w=None):
    r"""
    Returns the phase farfield for a
    `Laguerre-Gaussian <https://en.wikipedia.org/wiki/Gaussian_beam#Laguerre-Gaussian_modes>`_
    beam. Uses the formalism described by
    `this paper <https://doi.org/10.1364/JOSAA.25.001642>`_.

    Note
    ~~~~
    Without radial order (``p = 0``), this function distills to a
    `vortex waveplate <https://en.wikipedia.org/wiki/Optical_vortex>`_
    of given azimuthal order ``l``.

    Tip
    ~~~
    This function is especially useful to hone and validate SLM alignment. Perfect alignment will
    result in concentric and uniform fringes for higher order beams. Focusing issues, aberration,
    or pointing misalignment will mitigate this.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    l : int
        The azimuthal wavenumber, or orbital angular momentum. Can be negative.
    p : int
        The radial wavenumber. Should be non-negative.
    w : float OR None
        See :meth:`~slmsuite.holography.toolbox._determine_source_radius()`.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)

    w = _determine_source_radius(grid, w)

    theta_grid = np.arctan2(x_grid, y_grid)
    rr_grid = y_grid * y_grid + x_grid * x_grid

    return (
        l * theta_grid
        + np.pi * np.heaviside(-special.genlaguerre(p, np.abs(l))(2 * rr_grid / w / w), 0)
    )


def hermite_gaussian(grid, n, m, w=None):
    r"""
    Returns the phase farfield for a
    `Hermite-Gaussian <https://en.wikipedia.org/wiki/Gaussian_beam#Hermite-Gaussian_modes>`_
    beam. Uses the formalism described by `this paper <https://doi.org/10.1364/AO.54.008444>`_.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    n, m : int
        The horizontal ``n`` and vertical ``m`` wavenumbers. ``n = m = 0`` yields a flat
        phase and a Gaussian beam.
    w : float
        See :meth:`~slmsuite.holography.toolbox._determine_source_radius()`.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)
    w = _determine_source_radius(grid, w)

    factor = np.sqrt(2) / w

    # Generate the amplitude of a Hermite-Gaussian mode.
    phase = special.hermite(n)(factor * x_grid) * special.hermite(m)(factor * y_grid)

    # This is real, so the phase is just the sign of the mode. This produces a
    # checkerboard pattern. Probably could make this faster by bitflipping rows and columns.
    phase[phase < 0] = 0
    phase[phase > 0] = np.pi

    return phase


def ince_gaussian(grid, p, m, parity=1, ellipticity=1, w=None):
    r"""
    **(NotImplemented)** Returns the phase farfield for an
    `Ince-Gaussian <https://en.wikipedia.org/wiki/Gaussian_beam#Ince-Gaussian_modes>`_
    beam.
    `Consider <https://doi.org/10.1364/OL.29.000144>`_
    `using <https://doi.org/10.1364/AO.54.008444>`_
    `these <https://doi.org/10.3390/jimaging8050144>`_
    `references <https://en.wikipedia.org/wiki/Elliptic_coordinate_system>`_.

    Parameters
    ----------
    grid : (array_like, array_like) OR :class:`~slmsuite.hardware.slms.slm.SLM`
        Meshgrids of normalized :math:`\frac{x}{\lambda}` coordinates
        corresponding to SLM pixels, in ``(x_grid, y_grid)`` form.
        These are precalculated and stored in any :class:`~slmsuite.hardware.slms.slm.SLM`, so
        such a class can be passed instead of the grids directly.
    p : int
        Ince polynomial order.
    m : int
        Ince polynomial degree.
    parity : {1, -1, 0}
        Whether to produce an even (1), odd (-1), or helical (0) Ince polynomial. A helical
        polynomial is the linear combination of even and odd polynomials.

        .. math:: IG^h_{p,m} = IG^e_{p,m} + iIG^o_{p,m}

    ellipticity : float
        Ellipticity of the beam. The semifocal distance is equal to ``ellipticity * w``,
        where the foci are the points which define the elliptical coordinate system.
    w : float
        See :meth:`~slmsuite.holography.toolbox._determine_source_radius()`.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)
    w = _determine_source_radius(grid, w)

    if parity == 1:
        if not 0 <= m <= p:
            raise ValueError("{} is an invalid Ince polynomial.".format((p,m)))
    else:
        if not 1 <= m <= p:
            raise ValueError("{} is an invalid Ince polynomial.".format((p,m)))

    complex_grid = x_grid + 1j * y_grid

    factor = 1 / (w * np.sqrt(ellipticity / 2))

    elliptic_grid = np.arccosh(complex_grid * factor)

    raise NotImplementedError()


def matheui_gaussian(grid, r, q, w=None):
    """
    **(NotImplemented)** Returns the phase farfield for a
    `Matheui-Gaussian <https://doi.org/10.1364/AO.49.006903>`_ beam.

    Returns
    -------
    numpy.ndarray
        The phase for this function.
    """
    (x_grid, y_grid) = _process_grid(grid)
    w = _determine_source_radius(grid, w)

    raise NotImplementedError()

