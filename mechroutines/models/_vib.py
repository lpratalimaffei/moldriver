"""
  Handle vibrational data info
"""

import autorun
import automol.geom
from phydat import phycon
from mechlib.amech_io import printer as ioprinter
from mechlib.amech_io._path import job_path
from mechroutines.models import typ
from mechroutines.models import _tors as tors


def vib_analysis(spc_dct_i, pf_filesystems, spc_mod_dct_i,
                 run_prefix, zrxn=None):
    """ process to get freq
    """

    tors_strs = ['']

    rotors = tors.build_rotors(
        spc_dct_i, pf_filesystems, spc_mod_dct_i)

    if typ.nonrigid_tors(spc_mod_dct_i, rotors):
        tors_strs = tors.make_hr_strings(rotors)
        [_, hr_str, _, prot_str, _] = tors_strs

        freqs, imag, tors_zpe, pot_scalef = tors_projected_freqs_zpe(
            pf_filesystems, hr_str, prot_str, run_prefix, zrxn=zrxn)

        # Make final hindered rotor strings and get corrected tors zpe
        if typ.scale_1d(spc_mod_dct_i):
            rotors = tors.scale_rotor_pots(rotors, scale_factor=pot_scalef)
            tors_strs = tors.make_hr_strings(rotors)
            [_, hr_str, _, prot_str, _] = tors_strs
            _, _, tors_zpe, _ = tors_projected_freqs_zpe(
                pf_filesystems, hr_str, prot_str, run_prefix, zrxn=zrxn)
            # Calculate current zpe assuming no freq scaling: tors+projfreq

        zpe = tors_zpe + (sum(freqs) / 2.0) * phycon.WAVEN2EH

        # For mdhrv model no freqs needed in MESS input, zero out freqs lst
        if 'mdhrv' in spc_mod_dct_i['tors']['mod']:
            freqs = ()
    else:
        freqs, imag, zpe = read_harmonic_freqs(
            pf_filesystems, run_prefix, zrxn=zrxn)
        tors_zpe = 0.0

    freqs, zpe = scale_frequencies(
        freqs, tors_zpe,
        spc_mod_dct_i, scale_method='3c')

    return freqs, imag, zpe, tors_strs


def full_vib_analysis(spc_dct_i, pf_filesystems, spc_mod_dct_i,
                      run_prefix, zrxn=None):
    """ process to get freq
    """

    tors_strs = ['']
    freqs = []
    imag = []
    tors_zpe = 0.0
    sfactor = 1.0
    tors_freqs = []
    rt_freqs1 = []

    rotors = tors.build_rotors(
        spc_dct_i, pf_filesystems, spc_mod_dct_i)

    if typ.nonrigid_tors(spc_mod_dct_i, rotors):
        tors_strs = tors.make_hr_strings(rotors)
        [_, hr_str, _, prot_str, _] = tors_strs

        freqs, imag, tors_zpe, pot_scalef = tors_projected_freqs_zpe(
            pf_filesystems, hr_str, prot_str, run_prefix, zrxn=zrxn)

        # Make final hindered rotor strings and get corrected tors zpe
        if typ.scale_1d(spc_mod_dct_i):
            rotors = tors.scale_rotor_pots(rotors, scale_factor=pot_scalef)
            tors_strs = tors.make_hr_strings(rotors)
            [_, hr_str, _, prot_str, _] = tors_strs
            torsinf = tors_projected_freqs(
                pf_filesystems, hr_str, prot_str, run_prefix, zrxn=zrxn)
            freqs, imag, tors_zpe, sfactor, tors_freqs, rt_freqs1 = torsinf

        # For mdhrv model no freqs needed in MESS input, zero out freqs lst
        if 'mdhrv' in spc_mod_dct_i['tors']['mod']:
            freqs = ()
    else:
        freqs, imag, _ = read_harmonic_freqs(
            pf_filesystems, run_prefix, zrxn=zrxn)
        tors_zpe = 0.0

    return freqs, imag, tors_zpe, sfactor, tors_freqs, rt_freqs1


def read_harmonic_freqs(pf_filesystems, run_prefix, zrxn=None):
    """ Read the harmonic frequencies for the minimum
        energy conformer
    """
    # Get the harmonic filesys information
    [cnf_fs, _, min_cnf_locs, _, _] = pf_filesystems['harm']
    freqs, imag, zpe = read_locs_harmonic_freqs(
        cnf_fs, min_cnf_locs, run_prefix, zrxn=zrxn)
    return freqs, imag, zpe


def read_locs_harmonic_freqs(cnf_fs, cnf_locs, run_prefix, zrxn=None):
    """ Read the harmonic frequencies for a specific conformer
    """

    # probably should read freqs
    # Do the freqs obtain for two species for fake and pst
    if cnf_locs is not None:

        # Obtain geom and freqs from filesys
        geo = cnf_fs[-1].file.geometry.read(cnf_locs)
        hess = cnf_fs[-1].file.hessian.read(cnf_locs)
        ioprinter.reading('Hessian', cnf_fs[-1].path(cnf_locs))

        # Build the run filesystem using locs
        fml_str = automol.geom.formula_string(geo)
        vib_path = job_path(run_prefix, 'PROJROT', 'FREQ', fml_str)

        # Obtain the frequencies
        ioprinter.info_message(
            'Calling ProjRot to diagonalize Hessian and get freqs...')
        script_str = autorun.SCRIPT_DCT['projrot']
        freqs, _, imag_freqs, _ = autorun.projrot.frequencies(
            script_str, vib_path, [geo], [[]], [hess])

        # Calculate the zpve
        ioprinter.frequencies(freqs)
        zpe = (sum(freqs) / 2.0) * phycon.WAVEN2EH

        # Check imaginary frequencies and set freqs
        if zrxn is not None:
            if len(imag_freqs) > 1:
                ioprinter.warning_message(
                    'Saddle Point has more than',
                    'one imaginary frequency')
            imag = imag_freqs[0]
        else:
            imag = None

    else:
        ioprinter.error_message(
            'Reference geometry is missing for harmonic frequencies')

    return freqs, imag, zpe


def read_anharmon_matrix(pf_filesystems):
    """ Read a anharmonicity matrix from the SAVE filesystem for a
        species or transition state.
    """

    # Set up vpt2 level filesystem for rotational values
    [cnf_fs, cnf_path, min_cnf_locs, _, _] = pf_filesystems['vpt2']

    if cnf_path:
        xmat = cnf_fs[-1].file.anharmonicity_matrix.read(
            min_cnf_locs)
        ioprinter.reading('Anharm matrix', cnf_path)
    else:
        ioprinter.error_message('No anharm matrix at path', cnf_path)

    return xmat


def tors_projected_freqs_zpe(pf_filesystems, mess_hr_str, projrot_hr_str,
                             prefix, zrxn=None, conf=None):
    """ Get frequencies from one version of ProjRot
    """
    ret = tors_projected_freqs(
        pf_filesystems, mess_hr_str, projrot_hr_str,
        prefix, zrxn=zrxn, conf=conf)
    freqs, imag, tors_zpe, scale_factor, _, _ = ret

    return freqs, imag, tors_zpe, scale_factor


def tors_projected_freqs(pf_filesystems, mess_hr_str, projrot_hr_str,
                         run_pfx, zrxn=None, conf=None):
    """ Get frequencies from one version of ProjRot
    """
    # run_prefix = pf_filesystems['run_prefix']

    # Build the filesystems
    [harm_cnf_fs, _, harm_min_locs, _, _] = pf_filesystems['harm']
    [tors_cnf_fs, _, tors_min_locs, _, _] = pf_filesystems['tors']
    if conf:
        harm_min_locs = conf[1]
        harm_cnf_fs = conf[2]

    # Read info from the filesystem that is needed
    harm_geo = harm_cnf_fs[-1].file.geometry.read(harm_min_locs)
    hess = harm_cnf_fs[-1].file.hessian.read(harm_min_locs)
    tors_geo = tors_cnf_fs[-1].file.geometry.read(tors_min_locs)
    ioprinter.reading('Hessian', harm_cnf_fs[-1].path(harm_min_locs))

    fml_str = automol.geom.formula_string(harm_geo)
    vib_path = job_path(run_pfx, 'PROJROT', 'FREQ', fml_str, print_path=True)
    # tors_path = job_path(run_pfx, 'MESS', 'TORS', fml_str, print_path=True)

    # Calculate projeccted frequencies and associated information
    mess_script_str = autorun.SCRIPT_DCT['messpf']
    projrot_script_str = autorun.SCRIPT_DCT['projrot']
    dist_cutoff_dct1 = {('H', 'O'): 2.26767, ('H', 'C'): 2.26767}
    dist_cutoff_dct2 = {('H', 'O'): 2.83459, ('H', 'C'): 2.83459,
                        ('C', 'O'): 3.7807}

    proj_inf = autorun.projected_frequencies(
        mess_script_str, projrot_script_str, vib_path,
        mess_hr_str, projrot_hr_str,
        tors_geo, harm_geo, hess,
        dist_cutoff_dct1=dist_cutoff_dct1,
        dist_cutoff_dct2=dist_cutoff_dct2,
        saddle=(zrxn is not None))
    proj_freqs, proj_imag, _, harm_freqs, tors_freqs = proj_inf
    tors_zpe = 0.5 * sum(tors_freqs) * phycon.WAVEN2EH

    # NEW scale factor functions
    scale_factor = automol.prop.freq.rotor_scale_factor_from_harmonics(
        harm_freqs, proj_freqs, tors_freqs)

    return (proj_freqs, proj_imag, tors_zpe,
            scale_factor, tors_freqs, harm_freqs)


def scale_frequencies(freqs, tors_zpe,
                      spc_mod_dct_i, scale_method='c3'):
    """ Empirically scale the harmonic vibrational frequencies and harmonic
        zero-point energy (ZPVE) of a species or transition to account
        for anharmonic effects. The final ZPVE value also includes the ZPVEs
        of internal rotations which are not scaled.

        Scaling factors determined by the electronic structure
        method used to calculate the frequencies and ZPVE as well as the
        requested scaling method.

        :param freqs: harmonic frequencies [cm-1]
        :type freqs: tuple(float)
        :param tors_zpe:

    """

    thy_info = spc_mod_dct_i['vib']['geolvl'][1][1]
    method, basis = thy_info[1], thy_info[2]
    scaled_freqs, scaled_zpe = automol.prop.freq.anharm_by_scaling(
        freqs, method, basis, scale_method=scale_method)
    tot_zpe = scaled_zpe + tors_zpe

    return scaled_freqs, tot_zpe
