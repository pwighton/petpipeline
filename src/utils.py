

def compute_average(in_file, out_file=None):

    """
        A function to compute tehe average over all time frames
        for a given pet volume
        
        Parameters
        ----------
        in_file : str 
            input file path (str) for pet volume
        out_file : str 
            output file path (str) computed average

        Returns
        -------
        out_file : str 
            output file path (str) computed average
    """

    import os
    import nibabel as nib
    import numpy as np
    from nipype.utils.filemanip import split_filename

    pet_brain = nib.load(in_file)
    pet_brain_img = pet_brain.get_fdata()
    avg = np.mean(pet_brain_img, axis=3)
    pet_brain_frame = nib.Nifti1Image(avg, pet_brain.affine)
        
    new_pth = os.getcwd()
    pth, fname, ext = split_filename(in_file)
    pet_brain_filename = "{}_mean.nii.gz".format(fname)
    pet_brain_frame.to_filename(pet_brain_filename)

    return os.path.abspath(pet_brain_filename)

def compute_weighted_average(in_file, json_file, out_file=None): 

    """
        A function to compute a time weighted average over
        the time frames for a given pet volume

        Parameters
        ----------
        in_file : str 
            input file path (str) for pet volume
        out_file : str 
            output file path (str) computed average

        Returns
        -------
        out_file : str 
            output file path (str) computed average

    """   
        
    import numpy as np
    import os 
    import nibabel as nib
    import json
    from nipype.utils.filemanip import split_filename


    img = nib.load(in_file)        
    data = np.float32(img.get_fdata())

    with open(json_file, 'r') as f:
        desc = json.load(f)
        frames = np.float32(np.array(desc['FrameDuration'], dtype=float))

    data = np.sum(np.float32(data * frames),axis=3) / np.sum(frames)
      
    img_ = nib.Nifti1Image(data, img.affine)
            
    new_pth = os.getcwd()
    pth, fname, ext = split_filename(in_file)
    out_file = "{}_twa.nii.gz".format(fname)
    img_.to_filename(out_file)
    return os.path.abspath(out_file)