import sys
from pathlib import Path
import tempfile
import unittest
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compare_radiometry import compare
from audit_radiometry import offset_diagnostics
from eoasset.outputs import radiometry_status

class RadiometryAuditTests(unittest.TestCase):
    def test_hypotheses_compare_identical_pixel_support(self):
        a={'red':np.array([500.,2000.,np.inf]),'nir':np.array([3000.,4000.,4000.]),'scl':np.array([4,4,4])}
        r=offset_diagnostics(a)
        self.assertEqual(r['sample_land_pixels'],2)
        self.assertEqual(r['common_pixel_support']['pixels'],1)
        self.assertAlmostEqual(r['common_pixel_support']['median_ndvi']['-0.1'],.5)
        self.assertAlmostEqual(r['common_pixel_support']['median_ndvi']['0.0'],1/3)
        a['scl'][:]=9
        self.assertIsNone(offset_diagnostics(a)['hypotheses']['0.0']['negative_reflectance_fraction'])

    def test_cli_respects_config_pool_and_explicit_override(self):
        import json
        from unittest.mock import patch
        from test_project import config
        from eoasset.pipeline import main
        from eoasset.config import validate
        cfg=config();cfg['model']['candidate_pool']='research'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json';p.write_text(json.dumps(cfg))
            with patch('eoasset.pipeline.run') as run:
                self.assertEqual(main(['--config',str(p),'--cached-only']),0)
                self.assertEqual(run.call_args.args[0]['model']['candidate_pool'],'research')
                self.assertEqual(main(['--config',str(p),'--cached-only','--candidate-pool','stable']),0)
                self.assertEqual(run.call_args.args[0]['model']['candidate_pool'],'stable')
        cfg['model']['candidate_pool']='typo'
        with self.assertRaises(ValueError):validate(cfg)

    def test_missing_crs_and_nonfinite_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[str(Path(tmp)/n) for n in ['raw.tif','missing_crs.tif']]
            for path,crs in zip(files,['EPSG:32643',None]):
                with rasterio.open(path,'w',driver='GTiff',width=32,height=32,count=1,dtype='float32',crs=crs,transform=from_origin(600000,3500000,10,10)) as d:
                    x=np.full((32,32),500,dtype='float32');x[0,:]=np.inf;d.write(x,1)
            r=compare(files[0],files[0],Window(0,0,32,32))
            self.assertEqual(r['paired_pixels'],992)
            with self.assertRaises(ValueError):compare(files[1],files[1],Window(0,0,32,32))
            with self.assertRaises(ValueError):compare(files[0],files[0],Window(0,0,0,32))

    def test_known_offset_and_grid_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[str(Path(tmp)/n) for n in ['cog.tif','reference.tif','wrong.tif']]
            for path,value,shift in zip(files,[500,1500,1500],[0,0,10]):
                with rasterio.open(path,'w',driver='GTiff',width=32,height=32,count=1,dtype='uint16',crs='EPSG:32643',transform=from_origin(600000+shift,3500000,10,10),nodata=0) as d:
                    d.write(np.full((32,32),value,dtype='uint16'),1)
            r=compare(files[0],files[1],Window(0,0,32,32))
            self.assertEqual(r['fraction_difference_1000'],1.)
            self.assertEqual(compare(files[0],files[0],Window(0,0,32,32))['fraction_difference_0'],1.)
            with self.assertRaises(ValueError):compare(files[0],files[2],Window(0,0,32,32))
            with self.assertRaises(ValueError):compare(files[0],files[1],Window(0,0,64,64))

    def test_conflict_is_flagged_not_treated_as_calibration(self):
        i={'id':'scene','properties':{'earthsearch:boa_offset_applied':True},'assets':{'red':{'raster:bands':[{'offset':-.1}]}}}
        r=radiometry_status([i],'satellite')
        self.assertEqual(r['conflicting_scene_ids'],['scene'])
        self.assertEqual(radiometry_status([i],'synthetic')['status'],'not_applicable')
        i['properties']['earthsearch:boa_offset_applied']=False
        self.assertEqual(radiometry_status([i],'satellite')['status'],'provisional_unverified')
        self.assertEqual(radiometry_status([i],'satellite')['conflicting_scene_ids'],[])
