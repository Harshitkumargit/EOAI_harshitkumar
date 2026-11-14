"""Compare aligned raw COG/reference pixels; report evidence, never change calibration.

Use the same acquisition, product baseline and band. Reference must be an original
unscaled product, not a display image. Rasterio supports local paths and HTTPS.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window

def compare(cog, reference, window):
    if window.width <= 0 or window.height <= 0 or any(v != int(v) for v in (window.col_off,window.row_off,window.width,window.height)):
        raise ValueError('Window must have integer coordinates and positive dimensions.')
    with rasterio.open(cog) as a, rasterio.open(reference) as b:
        if a.crs is None or b.crs is None:
            raise ValueError('Both rasters need an explicit CRS.')
        if a.count != 1 or b.count != 1:
            raise ValueError('Use single-band source products, not RGB/display imagery.')
        if a.crs != b.crs or a.transform != b.transform or a.shape != b.shape:
            raise ValueError('Reference grids differ: do not compare unmatched pixels.')
        if window.col_off < 0 or window.row_off < 0 or window.col_off+window.width>a.width or window.row_off+window.height>a.height:
            raise ValueError('Window outside raster bounds.')
        x=a.read(1,window=window,masked=True).astype('float64')
        y=b.read(1,window=window,masked=True).astype('float64')
        # Exclude nodata and conversion-clamped dark pixels from offset estimation.
        good=~(np.ma.getmaskarray(x)|np.ma.getmaskarray(y)) & np.isfinite(x.data) & np.isfinite(y.data) & (x.data>1)&(y.data>1)
        delta=y.data[good]-x.data[good]
        if len(delta)<100:raise ValueError('Fewer than 100 valid paired pixels; choose another window.')
        return {'paired_pixels':len(delta),'reference_minus_cog_dn_quantiles':np.quantile(delta,[0,.05,.5,.95,1]).tolist(),
                'fraction_difference_0':float(np.mean(np.abs(delta)<=1)),
                'fraction_difference_1000':float(np.mean(np.abs(delta-1000)<=1)),
                'interpretation':'Difference 1000 supports a COG-applied subtraction; difference 0 supports unchanged DN. Verify product identity and reference calibration; this tool never overrides metadata.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cog',required=True);p.add_argument('--reference',required=True)
    p.add_argument('--window',type=int,nargs=4,metavar=('COL','ROW','WIDTH','HEIGHT'),required=True)
    a=p.parse_args()
    if min(a.window[2:])<1 or max(a.window[2:])>512:p.error('Window dimensions must be 1..512.')
    result={'cog':a.cog,'reference':a.reference,'window':a.window}
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT=25,GDAL_HTTP_MAX_RETRY=0):
            result.update(compare(a.cog,a.reference,Window(*a.window)))
    except Exception as exc:result['error']=str(exc)
    out=Path(__file__).resolve().parents[1]/'reports'/('radiometry_pair_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    out.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2));print(out)
    return 1 if 'error' in result else 0

if __name__=='__main__':raise SystemExit(main())
