from paraview.simple import *
import sys
case = sys.argv[1]; out = sys.argv[2]
def rd(regions, arrays=['T']):
    r = OpenFOAMReader(FileName=case + '/stage1_shield_50K_v2.foam'); r.UpdatePipelineInformation()
    r.MeshRegions = regions; r.CellArrays = arrays
    r.UpdatePipeline(max(r.TimestepValues) if len(r.TimestepValues) else 0); return r
probe = OpenFOAMReader(FileName=case + '/stage1_shield_50K_v2.foam'); probe.UpdatePipelineInformation()
avail = list(probe.GetProperty('MeshRegions').GetAvailable()); print('AVAIL', avail)
view = GetActiveViewOrCreate('RenderView'); view.ViewSize = [3000, 2300]; view.Background = [1,1,1]
try: view.UseColorPaletteForBackground = 0
except: pass
view.OrientationAxesVisibility = 0
def pick(sub): return [a for a in avail if sub in a]
def show_patch(names, color, opacity=1.0, rep='Surface', clipit=True):
    if not names: print('no patch for', names); return None
    r = rd(names); src = MergeBlocks(Input=r)
    if clipit:
        c = Clip(Input=src); c.ClipType = 'Plane'; c.ClipType.Origin = [0,0,0.17]; c.ClipType.Normal = [1,-1,0]
        try: c.Invert = 0
        except: pass
        src = c
    d = Show(src, view); d.SetRepresentationType(rep); d.ColorArrayName = ['CELLS','']; d.AmbientColor = color; d.DiffuseColor = color; d.Opacity = opacity
    return d
show_patch(pick('/domain0/patch/OVC'), [0.75,0.35,0.28], 0.22, 'Surface')            # outer vacuum can, translucent, cut open
show_patch(pick('/domain0/patch/warmPlate') + pick('/domain1/patch/warmPlate'), [0.78,0.33,0.24], 0.45, 'Surface')        # 300 K plate
show_patch(pick('/domain0/patch/shield_slave') + pick('shield_bottom'), [0.35,0.55,0.55], 0.6, 'Surface')  # first shield
show_patch(pick('/domain1/patch/coldPlate'), [0.18,0.28,0.35], 1.0, 'Surface', clipit=False)
# harness bundles coloured by T (full, not clipped)
coax = [a for a in avail if '/coax' in a and a.endswith('internalMesh')]
r = rd(coax); m = MergeBlocks(Input=r); d = Show(m, view); d.SetRepresentationType('Surface'); ColorBy(d, ('CELLS','T'))
lut = GetColorTransferFunction('T'); lut.ApplyPreset('Cool to Warm', True); lut.RescaleTransferFunction(50.0, 300.0)
d.SetScalarBarVisibility(view, True); bar = GetScalarBar(lut, view); bar.Title = 'harness T [K]'; bar.ComponentTitle = ''; bar.TitleFontSize = 46; bar.LabelFontSize = 40; bar.ScalarBarLength = 0.4; bar.WindowLocation = 'Any Location'; bar.Position = [0.88, 0.3]; bar.RangeLabelFormat = '%.0f'
view.CameraPosition = [1.5, -1.5, 1.7]; view.CameraFocalPoint = [0.0, 0.0, 0.16]; view.CameraViewUp = [0,0,1]
ResetCamera(view); GetActiveCamera().Dolly(1.3); Render(view)
SaveScreenshot(out, view, ImageResolution=[3000, 2300]); print('saved', out)
