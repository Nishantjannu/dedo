# Dynamic Environments with Deformable Objects

TODO: port the rest of the code and add documentation

Workshop page with paper+poster: https://sites.google.com/nvidia.com/do-sim/posters


**Table of Contents:**<br />
[Installation](#install)<br />
[Examples](#examples)<br />

<a name="install"></a>
## Installation

Optional initial step: create a new conda environment with
`conda create --name dedo python=3.8` and activate it with
`conda activate dedo`. Conda is not strictly needed;
alternatives like virtualenv can be used;
a direct install without using virtual environments is ok as well.

```
git clone https://github.com/contactrika/dedo
cd dedo
pip install numpy
pip install -e .
```


### Examples

```
python -m dedo.demo --env=HangBag-v0 --viz --debug
```

![misc/imgs/bag_begin.png](misc/imgs/bag_begin.png)
![misc/imgs/bag_end.png](misc/imgs/bag_end.png)

```
python -m dedo.demo --env=HangCloth-v0 --viz --debug
```

![misc/imgs/apron_begin.png](misc/imgs/apron_begin.png)
![misc/imgs/apron_end.png](misc/imgs/apron_end.png)


The above will only have anchor positions as the state (this is just for quick
testing). 

To get images as state use `--cam_resolution` flag as follows:

```
python -m dedo.demo --env=HangCloth-v0 --cam_resolution 200 --viz --debug
```

![misc/imgs/apron_rgb.png](misc/imgs/apron_rgb.png)

To load custom object you would first have to fill an entry in `DEFORM_INFO` in 
`task_info.py`. The key should the the `.obj` file path relative to `data/`:

```
DEFORM_INFO = {
...
    # An example of info for a custom item.
    'bags/bags_zehang/obj/normal/bag1-1.obj': {
        'deform_init_pos': [0, 0.47, 0.47],
        'deform_init_ori': [np.pi/2, 0, 0],
        'deform_scale': 0.1,
        'deform_elastic_stiffness': 1.0,
        'deform_bending_stiffness': 1.0,
        'deform_true_loop_vertices': [
            [0, 1, 2, 3]  # placeholder, since we don't know the true loops
        ]
    },
```

Then you can use `--override_deform_obj` flag:

```
python -m dedo.demo --env=HangBag-v0 --cam_resolution 200 --viz --debug \
    --override_deform_obj bags/bags_zehang/obj/normal/bag1-1.obj
```

![misc/imgs/bag_zehang.png](misc/imgs/bag_zehang.png)


For items not in `DEFORM_DICT` you will need to specify sensible defaults,
for example:

```
python -m dedo.demo --env=HangCloth-v0 --viz --debug \
  --override_deform_obj=generated_cloth/generated_cloth.obj \
  --deform_init_pos 0.02 0.41 0.63 --deform_init_ori 0 0 1.5708
```

Example of scaling up the custom mesh objects:
```
python -m dedo.demo --env=HangCloth-v0 --viz --debug \
   --override_deform_obj=generated_cloth/generated_cloth.obj \
   --deform_init_pos 0.02 0.41 0.55 --deform_init_ori 0 0 1.5708 \
   --deform_scale 2.0 --anchor_init_pos -0.10 0.40 0.70 \
   --other_anchor_init_pos 0.10 0.40 0.70
```
