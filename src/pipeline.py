import os
import glob

import nibabel as nib

# Input 
import bids
from bids import BIDSLayout, BIDSValidator
bids.config.set_option('extension_initial_dot', True) #suppress bids warning

from nipype.interfaces.io import SelectFiles

# Nipype 
import nibabel as nib
from nipype import Node, Function
from nipype.pipeline import Node, MapNode, Workflow

# Motion Correction
from nipype.interfaces import fsl

# IdentityInterface for mappings
from nipype.interfaces.utility import IdentityInterface

# DataSink 
from nipype.interfaces.io import DataSink

# Free Surfer 
from nipype.interfaces.freesurfer import ReconAll

# PET Surfer 
from nipype.interfaces.freesurfer import petsurfer



def PETWorkflow(experiment_dir, output_dir, working_dir, data_dir):

    preproc = Workflow(name='preprocessing')
    
    path = os.path.join(experiment_dir,data_dir)
    preproc.base_dir = os.path.join(experiment_dir, working_dir)
    fs_dir = os.path.join(experiment_dir, 'freesurfer')

    os.system('mkdir -p %s'%fs_dir)

    mcflirt = Node(fsl.MCFLIRT(), name="motion_correction")

    coreg = Node(fsl.FLIRT(),name="co_registration")

    twa = Node(Function(input_names=["in_file", "json_file"], output_names=["out_file"], function=compute_weighted_average), name="time_weighted_average")
    
    applyxfm = Node(fsl.FLIRT(apply_xfm=True), name="apply_xfm")

    reconall = Node(ReconAll(directive='all', subjects_dir=fs_dir),name="reconall")

    gtmseg = Node(petsurfer.GTMSeg(), name="gtmseg")

    
    layout = BIDSLayout(path)
    infosource = Node(IdentityInterface(fields=['subject_id','session_id']),name="infosource")
    infosource.iterables = [('subject_id', layout.get_subjects()), ('session_id', layout.get_sessions())]


    templates = {'anat': 'sub-{subject_id}/ses-{session_id}/anat/*_T1w.nii' , 
                'pet': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.nii.gz', 
                'json': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}
    
    selectfiles = Node(SelectFiles(templates, base_directory=os.path.join(experiment_dir,data_dir)), name="select_files")

    datasink = Node(DataSink(base_directory=experiment_dir, container= output_dir), name="datasink")
    

    preproc.connect([ (infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]), 
                                                (selectfiles, mcflirt, [('pet', 'in_file')]), 
                                                (mcflirt, twa, [('out_file','in_file')]),
                                                (selectfiles, twa, [('json', 'json_file')]),
                                                (selectfiles, coreg, [('anat', 'in_file')]),
                                                (twa, coreg, [('out_file', 'reference')]),
                                                (coreg, applyxfm, [('out_matrix_file', 'in_matrix_file')]),
                                                (selectfiles, applyxfm, [('anat', 'in_file')]), 
                                                (selectfiles, applyxfm,[('pet','reference')]),
                                                (infosource, reconall, [('subject_id','subject_id')]),
                                                (selectfiles, reconall, [('anat','T1_files')]), 
                                                (reconall, gtmseg, [('subject_id','subject_id')]),                              
                                                (mcflirt, datasink, [('out_file', 'preproc.@out')]),
                                                (twa, datasink, [('out_file', 'preproc.@twa')]),
                                                (coreg, datasink, [('out_file', 'preproc.@coreg')]),
                                                (coreg, datasink, [('out_matrix_file', 'preproc.@trans_mat')]),
                                                (applyxfm, datasink, [('out_file', 'preproc.@petcoreg')])
                                                 ])

    
    preproc.write_graph(graph2use="flat")
    preproc.run()
    
def compute_weighted_average(in_file, json_file, out_file=None):    
      
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

def validate_input(path_to_dir):
    ''' To complete
        Check if the data is in the required format:
        Uses BIDSValidator
            For each subject:
                Has a PET and MR image
    '''
    try:
        #BIDSValidator(path_to_dir).is_bids()
        layout = BIDSLayout(path_to_dir)
        subjects = layout.get_subjects()
        return layout
    except Exception as e:
        print(e)

def extract_frame(in_file, json_file, out_file=None):

    import os
    import nibabel as nib
    from nipype.utils.filemanip import split_filename

    print(os.getcwd())
    pet_brain = nib.load(in_file)
    pet_brain_img = pet_brain.get_fdata()[:,:,:,26]
    pet_brain_frame = nib.Nifti1Image(pet_brain_img, pet_brain.affine)
    
    new_pth = os.getcwd()
    pth, fname, ext = split_filename(in_file)
    pet_brain_filename = "{}_ef.nii.gz".format(fname)
    pet_brain_frame.to_filename(pet_brain_filename)

    return os.path.abspath(pet_brain_filename)

def compute_average(in_file, json_file, out_file=None):

    import os
    import nibabel as nib
    import numpy as np
    from nipype.utils.filemanip import split_filename

    print(os.getcwd())
    pet_brain = nib.load(in_file)
    pet_brain_img = pet_brain.get_fdata()
    avg = np.mean(pet_brain_img, axis=3)
    pet_brain_frame = nib.Nifti1Image(avg, pet_brain.affine)
    
    new_pth = os.getcwd()
    pth, fname, ext = split_filename(in_file)
    pet_brain_filename = "{}_mean.nii.gz".format(fname)
    pet_brain_frame.to_filename(pet_brain_filename)

    return os.path.abspath(pet_brain_filename)


if __name__ == "__main__":
    
    # Specify experiment dir
    experiment_dir = "/home/avneet/Desktop/PETWorkflow"
    output_dir = 'output_dir/'  
    working_dir = 'working_dir/'
    data_dir = "data/"
    PETWorkflow(experiment_dir, output_dir, working_dir, data_dir)