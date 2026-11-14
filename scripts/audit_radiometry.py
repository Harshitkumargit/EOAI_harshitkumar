"""Read a small AOI sample for radiometry diagnosis; never alter production data."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from eoasset.grid import make_grid
from eoasset.config import load_config
from eoasset.ingest import _cog_href

def offset_diagnostics(arrays):
    land=np.isin(arrays['scl'],[4,5]) & np.isfinite(arrays['red']) & np.isfinite(arrays['nir']) & (arrays['red']>0) & (arrays['nir']>0)
    hypotheses={}; values={}; masks={}
    for offset in [-.1,0.]:
        red=arrays['red']*.0001+offset;nir=arrays['nir']*.0001+offset
        good=land & (red>=0)&(nir>=0)&((red+nir)>1e-6)
        index=np.full(red.shape,np.nan)
        np.divide(nir-red,nir+red,out=index,where=good)
        values[str(offset)]=index;masks[str(offset)]=good
        hypotheses[str(offset)]={'negative_reflectance_fraction':float((land&((red<0)|(nir<0))).sum()/land.sum()) if land.any() else None,
            'retained_pixels':int(good.sum()),'median_ndvi':float(np.median(index[good])) if good.any() else None}
    common=masks['-0.1'] & masks['0.0']
    paired={'pixels':int(common.sum()),'median_ndvi':{k:float(np.median(v[common])) if common.any() else None for k,v in values.items()},
            'median_ndvi_difference':float(np.median((values['-0.1']-values['0.0'])[common])) if common.any() else None}
    return {'sample_land_pixels':int(land.sum()),'hypotheses':hypotheses,'common_pixel_support':paired}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--ids',nargs='+',required=True)
    args=parser.parse_args()
    items=json.loads(args.sources.read_text())
    if isinstance(items,dict):items=items.get('features',items.get('items',[]))
    cfg=load_config(ROOT/'config.json');grid=make_grid(cfg)
    result=[]
    for item in items:
        if item['id'] not in args.ids:continue
        record={'id':item['id'],'boa_offset_applied':item['properties'].get('earthsearch:boa_offset_applied'),
                'baseline':item['properties'].get('s2:processing_baseline'),'bands':{}}
        try:
            arrays={}
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT=30,GDAL_HTTP_MAX_RETRY=1):
                for band in ['red','nir','scl']:
                    asset=item['assets'][band]
                    with rasterio.open(_cog_href(asset['href'],'regional_path')) as src:
                        record['bands'][band]={'asset_metadata':asset.get('raster:bands'),
                                              'tiff_scales':src.scales,'tiff_offsets':src.offsets}
                        with WarpedVRT(src,crs=grid.crs,transform=grid.transform,width=grid.labels.shape[1],height=grid.labels.shape[0],resampling=Resampling.nearest) as vrt:
                            arrays[band]=vrt.read(1,out_shape=(256,256),masked=True).astype(float).filled(np.nan)
            record.update(offset_diagnostics(arrays))
        except Exception as exc:record['error']=str(exc)
        result.append(record)
        print(json.dumps(record,indent=2))
    out=ROOT/'reports'/('radiometry_sample_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    missing=sorted(set(args.ids)-{r['id'] for r in result})
    out.write_text(json.dumps({'note':'Nearest-neighbor 256x256 AOI diagnostic, not corrected training data. Plausibility does not prove the correct offset.','scenes':result,'missing_requested_ids':missing},indent=2,allow_nan=False),encoding='utf-8')
    print(out)
    return 1 if missing or any('error' in r for r in result) else 0

if __name__=='__main__':raise SystemExit(main())

