import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import orca_ped_analyzer as a
from orca_ped_analyzer_gui import _find_ir_dat_files


def write_hess(path):
    """Synthetic bent triatomic with known 10, 100, 200 cm-1 vibrations."""
    xyz=np.array([[1.8,0,0],[0,0,0],[-.5,1.7,0]])
    masses=np.array([1.,16.,1.])
    true_b=np.array([a.b_row(a.IC('bond',(0,1)),xyz),
                     a.b_row(a.IC('bond',(1,2)),xyz),
                     a.b_row(a.IC('angle',(0,1,2)),xyz)])
    invsqrt=np.repeat(1/np.sqrt(masses),3)
    q,_=np.linalg.qr((true_b*invsqrt).T)
    hmw=q@np.diag((np.array([10.,100.,200.])/a.FREQ_FACTOR)**2)@q.T
    h=hmw/invsqrt[:,None]/invsqrt[None,:]
    freqs,modes=a.reconstruct_modes(h,masses)
    freqs[:6]=0
    def matrix(name,values):
        lines=['$'+name, f'{values.shape[0]} {values.shape[1]}',
               ' '.join(map(str,range(values.shape[1])))]
        lines += [str(i)+' '+' '.join(f'{v:.16e}' for v in row)
                  for i,row in enumerate(values)]
        return '\n'.join(lines)+'\n'
    text=matrix('hessian',h)+matrix('normal_modes',modes)
    text+='$atoms\n3\n'
    for elem,m,r in zip(['H','O','H'],masses,xyz):
        text+=f'{elem} {m} '+' '.join(map(str,r))+'\n'
    text+='$vibrational_frequencies\n9\n'
    text+=''.join(f'{i} {f:.12f}\n' for i,f in enumerate(freqs))
    text+='$ir_spectrum\n9\n'
    text+=''.join(f'{f:.12f} 0.01 0.1 0.0 0.0\n' for f in freqs)
    text+='$end\n'
    path.write_text(text)


def write_vpt2(path, frequencies=(9.,95.,190.)):
    path.write_text('ORCA VPT2/GVPT2 Analysis\nFundamental transitions [1/cm]\n'+
                    ''.join(f'{i} {h} {f} {f-h}\n'
                            for i,(h,f) in enumerate(zip([10.,100.,200.],frequencies)))+
                    'Overtones and combination bands\n0 0 18 0.1 1 0.01 0.1 0 0\n'
                    '========= End =========\n')


def run_cli(hess,*args):
    out=io.StringIO()
    with patch('sys.argv',['orca_ped_analyzer',str(hess),'--no-avogadro-cjson',*args]), \
         contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
        a.main()
    return out.getvalue()


class CoordinateTests(unittest.TestCase):
    def test_near_linear_b_has_no_rigid_motion_and_preserves_force_field(self):
        for angle in (177.,179.9):
            with self.subTest(angle=angle):
                t=np.deg2rad(angle)
                xyz=np.array([[2.,0,0],[0,0,0],[2*np.cos(t),2*np.sin(t),0.]])
                cs=a.generate_candidates(['O','C','O'],xyz,[(0,1),(1,2)])
                bc=a.vibrational_b_matrix(np.array([a.b_row(c,xyz) for c in cs]),xyz)
                b=bc[a.select_nonredundant(cs,bc,3)]
                for e in np.eye(3):
                    np.testing.assert_allclose(b@np.cross(e,xyz).ravel(),0,atol=1e-10)
                    np.testing.assert_allclose(b@np.tile(e,3),0,atol=1e-10)
                true=np.array([a.b_row(a.IC('bond',(0,1)),xyz),
                               a.b_row(a.IC('bond',(1,2)),xyz),
                               a.b_row(a.IC('angle',(0,1,2)),xyz)])
                h=true.T@np.diag([1.,1.,.2])@true
                bi=np.linalg.pinv(b); f=bi.T@h@bi
                self.assertLess(np.linalg.norm(h-b.T@f@b)/np.linalg.norm(h),1e-6)
                freq,modes=a.reconstruct_modes(h,np.array([16.,12.,16.]))
                d=b@modes[:,a.vibrational_mode_indices(freq,3)]
                for method in ('ped','ted'):
                    pct,_=a.compute_energy_distribution(b,f,d,[16.,12.,16.],method)
                    np.testing.assert_allclose(pct.sum(axis=0),100,atol=1e-8)

    def test_exact_linear_molecule_keeps_two_bends(self):
        xyz=np.array([[2.,0,0],[0,0,0],[-2.,0,0]])
        cs=a.generate_candidates(['O','C','O'],xyz,[(0,1),(1,2)])
        original=np.array([a.b_row(c,xyz) for c in cs])
        b=a.vibrational_b_matrix(original,xyz)
        np.testing.assert_allclose(b,original,atol=1e-10)
        self.assertEqual(len(a.select_nonredundant(cs,b,4)),4)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.hess=self.root/'molecule.hess'
        write_hess(self.hess)
        self.outdir=self.root/'molecule_analysis'

    def test_low_frequency_filter_does_not_break_vpt2_or_ir(self):
        write_vpt2(self.hess.with_suffix('.out'))
        log=run_cli(self.hess)
        self.assertIn('COMPLETE + VALID',log)
        with (self.outdir/'molecule_summary.csv').open() as f:
            rows=list(csv.DictReader(f))
        self.assertEqual([r['vpt2_mode'] for r in rows],['1','2'])
        self.assertEqual([float(r['vpt2_fundamental_cm-1']) for r in rows],[95.,190.])
        spectrum=self.outdir/'molecule_IR_fundamentals.dat'
        self.assertIn('fundamental_frequency_source=VPT2',spectrum.read_text())
        data=np.loadtxt(spectrum)
        self.assertGreater(data[np.argmin(abs(data[:,0]-9)),1],0)

    def test_csv_exports_every_coordinate_despite_display_limits(self):
        for method in ('ped','ted'):
            run_cli(self.hess,'--top','1','--min-percent','99',
                    '--energy-distribution',method)
            with (self.outdir/f'molecule_{method}.csv').open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),6)  # two reported modes, three ICs each
            for mode in ('7','8'):
                self.assertAlmostEqual(sum(float(r['percent']) for r in rows
                                           if r['mode']==mode),100.)

    def test_invalid_vpt2_rerun_removes_old_spectra(self):
        output=self.hess.with_suffix('.out')
        write_vpt2(output)
        run_cli(self.hess)
        self.assertTrue((self.outdir/'molecule_IR_complete.dat').exists())
        write_vpt2(output,(-5.,95.,190.))
        log=run_cli(self.hess)
        self.assertIn('Non-positive',log)
        self.assertFalse((self.outdir/'molecule_IR_complete.dat').exists())
        self.assertFalse((self.outdir/'molecule_IR_anharmonic.dat').exists())
        # Another calculation's file must not be displayed or deleted.
        other=self.outdir/'other_IR_complete.dat'; other.write_text('untouched')
        files=_find_ir_dat_files(self.outdir,'molecule_manifest.txt')
        self.assertEqual([p.name for p in files],['molecule_IR_fundamentals.dat'])
        run_cli(self.hess,'--no-ir-spectra')
        self.assertEqual(_find_ir_dat_files(self.outdir,'molecule_manifest.txt'),[])
        self.assertEqual(other.read_text(),'untouched')

    def test_nonpositive_or_nonfinite_vpt2_is_invalid(self):
        output=self.hess.with_suffix('.out')
        for bad in (-50.,0.,float('nan'),float('inf')):
            with self.subTest(bad=bad):
                write_vpt2(output,(bad,95.,190.))
                result=a.parse_vpt2_output(output,3,[10.,100.,200.])
                self.assertEqual(result['status'],'complete-invalid')


if __name__=='__main__':
    unittest.main()
