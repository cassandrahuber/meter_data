# Harvest

### **Code Guide:**

1. [harvest_orig.ipynb](notebooks/harvest_orig.ipynb)
   * Preprocessing data
2. [harvest_kwh.ipynb](notebooks/harvest_kwh.ipynb)
   * Processing kwh
   * Other (extra)
3. [harvest_kw.ipynb](notebooks/harvest_kw.ipynb)
   * Processing kw
4. [harvest_comparison_aurora_kw.ipynb](notebooks/harvest_comparison_aurora_kw.ipynb)
   * Comparing Harvest vs. Aurora
5. [harvest_aurora_kwh.ipynb](notebooks/harvest_aurora_kwh.ipynb)
   * Processing kwh for Aurora using Harvest code

* Self defined modules (first-read guide: [modules/README.md](modules/README.md)):
  * [harvest_orig.py](modules/harvest_orig.py)
  * [harvest_kwh.py](modules/harvest_kwh.py)
  * [harvest_kw.py](modules/harvest_kw.py)
  * [harvest_kw_comp.py](modules/harvest_kw_comp.py)
  * [file_naming.py](modules/file_naming.py)
  * [find_missing_data.py](modules/find_missing_data.py) (extra)


### **Environment:**

Can recreate my same Python setup with the following commands in terminal

```ruby
$ conda env create -f environment.yml
$ conda activate harvest
```


