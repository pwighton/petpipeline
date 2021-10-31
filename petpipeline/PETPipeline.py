import os
import glob

import nibabel as nib

# Input 
import bids
from bids import BIDSLayout, BIDSValidator
from nipype.interfaces.freesurfer.model import SegStatsReconAllInputSpec

bids.config.set_option('extension_initial_dot', True) #suppress bids warning

from nipype.interfaces.io import SelectFiles

# Nipype 
import nibabel as nib
from nipype import Node, Function
from nipype.pipeline import Node, MapNode, Workflow

# FSL for Motion Correction
from nipype.interfaces import fsl

# IdentityInterface for mappings
from nipype.interfaces.utility import IdentityInterface

# DataSink for storing outputs
from nipype.interfaces.io import DataSink

# Free Surfer for ReconAll
from nipype.interfaces.freesurfer import ReconAll

# PET Surfer for Delineation of Volumes of Interest, Partial Volume Correction, Kinetic Modelling
from nipype.interfaces.freesurfer import petsurfer

# MRICoreg for Coregistration
from nipype.interfaces.freesurfer import MRICoreg

# Helper functions
from utils import *

from config import _EnvConfig, \
                   _ReconAllConfig, \
                   _MotionCorrectionConfig, \
                   _PartialVolumeCorrectionConfig, \
                   _CoregistrationConfig


class PETPipeline:

    def __init__(self, **kwargs):

        self.__dict__.update(kwargs)

        # inititalize workflow
        self.preprocessing_workflow = Workflow(name='preprocessing')        
        self.preprocessing_workflow.base_dir = os.path.join(self.env_config.experiment_dir, 
                                                            self.env_config.working_dir)
        # data path
        self.data_path = os.path.join(self.env_config.experiment_dir,self.env_config.data_dir)

        # create freesurfer dir
        self.freesurfer_dir = os.path.join(self.env_config.experiment_dir, 'freesurfer')
        assert_dir(self.freesurfer_dir)

        # create derivatives
        self.derivatives = os.path.join(self.env_config.experiment_dir, 'derivatives')
        assert_dir(self.derivatives)
        
        # create pvc_dir
        self.pvc_dir = os.path.join(self.derivatives,'pvc')
        assert_dir(self.pvc_dir)

        # create km_dir
        self.km_dir = os.path.join(self.derivatives,'km')
        assert_dir(self.km_dir)

        # create km2_dir
        self.km2_dir = os.path.join(self.derivatives,'km2')
        assert_dir(self.km2_dir)
        

    def PETWorkflow(self):

        """
            Create a workflow for PET preprocessing.
        """

        # 1. Motion Correction
        motion_correction = Node(fsl.MCFLIRT(
                                             **self.motion_correction_config.__dict__), 
                                              name="motion_correction")


        # time weighted average
        time_weighted_average = Node(Function(
                                        input_names=["in_file", "json_file"], 
                                        output_names=["out_file"], 
                                        function=compute_weighted_average), 
                                        name="time_weighted_average")
                                    
        
        # 2. Co-Registration
        coregistration = Node(MRICoreg(
                                **self.coregistration_config.__dict__,
                                subjects_dir=self.freesurfer_dir),
                                name="coregistration")

        # 3.a. Delineation of Volumes of Interest: Run Reconall for all subjects
        reconall = Node(ReconAll(
                            directive='all', 
                            subjects_dir=self.freesurfer_dir),
                            name="reconall")

        # 3.b. Delineation of Volumes of Interest: Pet Surfer GTMSeg
        gtmseg = Node(petsurfer.GTMSeg(
                        subjects_dir=self.freesurfer_dir),
                        name="gtmseg")
  

        mapsubjects = Node(Function(
                            input_names=['session_id','subject_id'], 
                            output_names=['subject_id'], 
                            function=self.map_subjects), name="mapsubjects")

        create_subjects_dir_pvc = Node(Function(
                                        input_names=['directory','session_id','subject_id'],
                                        output_names=['directory'], 
                                        function = self.create_subjects_dir
                                       ),name= "create_subjects_dir_pvc")
        create_subjects_dir_pvc.inputs.directory = self.pvc_dir

        # 4. Partial Volume Correction 
        partial_volume_correction = Node(petsurfer.GTMPVC(
                                            **self.pvc_config.__dict__,
                                            subjects_dir=self.freesurfer_dir),
                                            name="partial_volume_correction")
        
        # 5. a. Kinetic Modelling using MRTM
        midframes = Node(Function(
                            input_names=['json_file'], 
                            output_names=['time_file'], 
                            function=create_mid_frame_dat), name="midframes")

        
        combine_outputs = Node(Function (input_names=["time_file","ref_file"],
                                        output_names = ["input_to_mrtm"],
                                        function = combine_file_paths),
                                        name="combine_outputs")

        
        create_subjects_dir_km = Node(Function(
                                        input_names=['directory','session_id','subject_id'],
                                        output_names=['directory'], 
                                        function = self.create_subjects_dir
                                       ),name= "create_subjects_dir_km")
        create_subjects_dir_km.inputs.directory = self.km_dir
        kinetic_modelling = Node(petsurfer.MRTM(subjects_dir=self.freesurfer_dir),name="kinetic_modelling")


        # 5. b. Kinetic Modelling using MRTM2
        
        combine_outputs_ = Node(Function(input_names=["time_file","ref_file", "k2p_file"],
                                        output_names = ["input_to_mrtm2"],
                                        function = combine_),
                                        name="combine_")

        create_subjects_dir_km2 = Node(Function(
                                        input_names=['directory','session_id','subject_id'],
                                        output_names=['directory'], 
                                        function = self.create_subjects_dir
                                       ),name= "create_subjects_dir_km2")
        create_subjects_dir_km2.inputs.directory = self.km2_dir
        kinetic_modelling_ = Node(petsurfer.MRTM2(subjects_dir=self.freesurfer_dir),name="kinetic_modelling_")



        # Streamline Input Output
        layout = BIDSLayout(self.data_path)
        infosource = Node(IdentityInterface(
                            fields=['subject_id','session_id']),
                            name="infosource")
        infosource.iterables = [('subject_id', layout.get_subjects()), ('session_id', layout.get_sessions())]


        templates = {'anat': 'sub-{subject_id}/ses-{session_id}/anat/*_T1w.nii', 
                    'pet': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.nii.gz', 
                    'json': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}
           
        selectfiles = Node(SelectFiles(templates, base_directory=os.path.join(self.env_config.experiment_dir,self.env_config.data_dir)), name="select_files")


        #petsurfer_templates = {'': 'sub-{subject_id}/ses-{session_id}/*_.dat}
        
        datasink = Node(DataSink(base_directory=self.derivatives, container="petsurfer"), name="datasink")

       
        substitutions = [('_subject_id_', 'sub-')]
        subjFolders = [('_session_id_%ssub-%s' % (ses, sub), 'sub-%s/ses-%s' %(sub,ses))
                        for ses in layout.get_sessions()
                        for sub in layout.get_subjects()]
        substitutions.extend(subjFolders)
        datasink.inputs.substitutions = substitutions

        

        self.preprocessing_workflow.connect([
                                                (infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]), 
                                                (infosource, mapsubjects, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                (selectfiles, motion_correction, [('pet', 'in_file')]), 
                                                (motion_correction, time_weighted_average, [('out_file','in_file')]),
                                                (selectfiles, time_weighted_average, [('json', 'json_file')]),
                                                (selectfiles, reconall, [('anat','T1_files')]),
                                                (mapsubjects, reconall, [('subject_id','subject_id')]),
                                                (reconall, gtmseg, [('subject_id','subject_id')]),
                                                (reconall, coregistration, [('subject_id','subject_id')]),
                                                (time_weighted_average, coregistration, [('out_file','source_file')]),
                                                (selectfiles, coregistration, [('anat','reference_file')]),
                                                (motion_correction, partial_volume_correction, [('out_file','in_file')]),
                                                (infosource, create_subjects_dir_pvc, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                (gtmseg, partial_volume_correction, [('gtm_file','segmentation')]),
                                                (coregistration, partial_volume_correction, [('out_lta_file','reg_file')]),
                                                (create_subjects_dir_pvc,partial_volume_correction, [('directory','pvc_dir')]),
                                                (partial_volume_correction, combine_outputs, [('ref_file','ref_file')]),
                                                (selectfiles,midframes, [('json','json_file')]),
                                                (midframes, combine_outputs, [('time_file','time_file')]),
                                                (combine_outputs, kinetic_modelling ,[('input_to_mrtm', 'mrtm1')]),
                                                (infosource, create_subjects_dir_km, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                (create_subjects_dir_km, kinetic_modelling ,[('directory', 'glm_dir')]),
                                                (partial_volume_correction, kinetic_modelling ,[('hb_nifti','in_file')]),
                                                (kinetic_modelling, datasink, [('k2p','trythis2')]),
                                                (kinetic_modelling, combine_outputs_, [('k2p','k2p_file')]),
                                                (partial_volume_correction, datasink, [('hb_nifti','trythis')]),
                                                (midframes, combine_outputs_, [('time_file','time_file')]),
                                                (partial_volume_correction, combine_outputs_, [('ref_file','ref_file')]),
                                                (combine_outputs_, kinetic_modelling_, [('input_to_mrtm2','mrtm2')]),
                                                (infosource, create_subjects_dir_km2, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                (create_subjects_dir_km2, kinetic_modelling_ ,[('directory', 'glm_dir')]),
                                                (partial_volume_correction, kinetic_modelling_ ,[('hb_nifti','in_file')]),
                                                ])
    
    def create_subjects_dir(directory, session_id, subject_id):
        """
            Map session ids and subject ids to 
            correcsponding directories for 
            'pvc_dir' inputs to partial volume correction 

            Parameters
            ----------
            session_id : str 
                session identifier
            subject_id : str 
                unique subject identifier 

            Returns
            -------
            path to dir session_id_subject_id: str
                creates directory  for each session and subject combined
                for storing pvc output
        """
        from pathlib import Path
        import os

        dir_name = "sub-" +  subject_id + "/" + "ses-" + session_id
        dir_path = os.path.join(directory,dir_name)
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        return os.path.abspath(dir_path)
            

    
    def map_subjects(session_id, subject_id):
        """
            Map session ids and subject ids for for recon all 

            Parameters
            ----------
            session_id : str 
                session identifier
            subject_id : str 
                unique subject identifier 

            Returns
            -------
            session_id_subject_id: str
                unique identifier for each session and subject combined
                for storing freesurfer output
        """
        return (session_id + "_" + subject_id)
    
    def run(self):
        self.preprocessing_workflow.write_graph(graph2use="flat")
        self.preprocessing_workflow.run()