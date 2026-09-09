from probe_empty_cad_edges import peaks

def test_no_signal():
    assert peaks([0]*20,10,100)==[]

def test_competing_peaks_and_origin():
    p=[0.]*40
    p[10],p[11],p[17],p[25]=9,8,7,6
    r=peaks(p,15,100)
    assert [v['coordinate_px'] for v in r]==[110.5,117.5,125.5]
    assert r[0]['delta_from_CAD_px']==-4.5

def test_nan_and_window():
    assert peaks([float('nan'),2,0,0,0,100],1,0,radius=1)[0]['coordinate_px']==1.5
