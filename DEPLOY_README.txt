LABEL QC CHECKER PRO - FINAL RENDER DEPLOYMENT PACKAGE

1. Extract this ZIP.
2. Open the extracted LabelQCCheckerPro_FINAL folder.
3. Create a NEW empty GitHub repository.
4. Upload ALL files and folders inside this folder to the ROOT of the GitHub repository.
   IMPORTANT: the engine folder must be directly in the repository root.
5. Confirm the repository contains:
   app.py
   config.py
   requirements.txt
   Dockerfile
   render.yaml
   templates/
   engine/
6. In Render, create a Web Service from the GitHub repository.
7. Select Docker, branch main, Dockerfile ./Dockerfile, build context .
8. Deploy.

Do not upload the outer LabelQCCheckerPro_FINAL folder itself as a nested folder.
The GitHub repository root must contain app.py and the engine folder directly.
