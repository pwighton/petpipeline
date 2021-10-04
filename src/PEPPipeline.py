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

# Coregistration
from nipype.interfaces.freesurfer import MRICoreg

class PETPipeline:

    preproc = None

    def __init__(self, experiment_dir, working_dir, output_dir, data_dir):
        self.experiment_dir = experiment_dir
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.data_dir = data_dir 

    def PETWorkflow(self):

        # inititalize workflow
        self.preproc = Workflow(name='preprocessing')

        path = os.path.join(self.experiment_dir,self.data_dir)
        self.preproc.base_dir = os.path.join(self.experiment_dir, self.working_dir)

        # create freesurfer dir
        fs_dir = os.path.join(self.experiment_dir, 'freesurfer')
        os.system('mkdir -p %s'%fs_dir)

        # Initialize nodes in workflow

        # 1. Motion Correction
        mcflirt = Node(fsl.MCFLIRT(), name="motion_correction")

        #coreg = Node(fsl.FLIRT(),name="co_registration")
        #applyxfm = Node(fsl.FLIRT(apply_xfm=True), name="apply_xfm")

        # time weighted average
        twa = Node(Function(input_names=["in_file", "json_file"], output_names=["out_file"], 
                function=self.compute_weighted_average), name="time_weighted_average")
        
        # 2. Co-Registration
        mricoreg = Node(MRICoreg(subjects_dir=fs_dir),name="mricoreg")

        # 3.a. Delineation of Volumes of Interest: Run Reconall for all subjects
        reconall = Node(ReconAll(directive='all', subjects_dir=fs_dir),name="reconall")

        # 3.b. Delineation of Volumes of Interest: Pet Surfer GTMSeg
        gtmseg = Node(petsurfer.GTMSeg(subjects_dir=fs_dir), name="gtmseg")
  

        getiterlist = Node(Function(input_names=['session_id','subject_id'], 
                        output_names=['subject_id'], function=self.map_subjects), name="getiterlist")

        # 4. Partial Volume Correction 
        mrigtmpvc = Node(petsurfer.GTMPVC(subjects_dir=fs_dir), name="gtmpvc")
        

        # Streamline Input Output 
        layout = BIDSLayout(path)
        infosource = Node(IdentityInterface(fields=['subject_id','session_id']),name="infosource")
        infosource.iterables = [('subject_id', layout.get_subjects()), ('session_id', layout.get_sessions())]


        templates = {'anat': 'sub-{subject_id}/ses-{session_id}/anat/*_T1w.nii', 
                    'pet': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.nii.gz', 
                    'json': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}
           
        selectfiles = Node(SelectFiles(templates, base_directory=os.path.join(self.experiment_dir,self.data_dir)), name="select_files")

        
        datasink = Node(DataSink(base_directory=self.experiment_dir, container= self.output_dir), name="datasink")
        
        self.preproc.connect([(infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]), 
                              (infosource, getiterlist, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                    (selectfiles, mcflirt, [('pet', 'in_file')]), 
                                                    (mcflirt, twa, [('out_file','in_file')]),
                                                    (selectfiles, twa, [('json', 'json_file')]),
                                                    (selectfiles, reconall, [('anat','T1_files')]),
                                                    (getiterlist, reconall, [('subject_id','subject_id')]),
                                                    (reconall, gtmseg, [('subject_id','subject_id')]),
                                                    (reconall, mricoreg, [('subject_id','subject_id')]), 
                                                    (twa, mricoreg, [('out_file','source_file')]),
                                                    (selectfiles, mricoreg, [('anat','reference_file')]),
                                                    (mcflirt, mrigtmpvc, [('out_file','in_file')]),
                                                    (mricoreg,datasink,[('out_lta_file','preproc.@gtmseg')]),
                                                    (gtmseg, mrigtmpvc, [('out_file','segmentation')]),
                                                    (mricoreg, mrigtmpvc, [('out_lta_file','reg_file')])])


    def run(self):
        self.preproc.write_graph(graph2use="flat")
        self.preproc.run()

    # Helper functions
    def compute_average(self, in_file, json_file, out_file=None):

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

    def compute_weighted_average(self, in_file, json_file, out_file=None):    
        
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



    def map_subjects(self, session_id, subject_id):
        """
            Map session ids and subject ids for for recon all 
        """
        return (session_id + "_" + subject_id)

if __name__== "__main__":
    experiment_dir = "/home/avneet/Desktop/PETWorkflow_"
    output_dir = 'output_dir/'  
    working_dir = 'working_dir/'
    data_dir = "data/"

    pipeline = PETPipeline(experiment_dir, output_dir, working_dir, data_dir)
    pipeline.PETWorkflow()
    pipeline.run()