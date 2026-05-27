# GitHub Quick Git Cheat Sheet
# this is a workflow from a fresh start. Skip git switch main if alreay on local repo. 
## git add . stages everything in the current folder
## git clone w/ . at end stages it to the currently open folder. Do this if you created the folder before setting up the repo
### ALL OF THIS IS FOR LOCAL MANAGEMENT

```bash
cd E:\2026_vtpk
git clone https://github.com/ForestJenna/General-Helpers.git LocalRepo
OR
git clone https://github.com/ForestJenna/General-Helpers.git . 
cd LocalRepo
git switch main
git pull origin main
git switch -c my-new-branch
git add . 
git commit -m "Describe your changes"
git push -u origin my-new-branch
git status
```

# To get the local to agree with the main on GitHub
```bash
git switch main
git pull origin main
git merge First-Branch-Trans-Track-Vdata
git push origin main
```

# Safe clean up steps after the branches are merged to main.
```bash
git switch main
git fetch origin
git branch -d First-Branch-Trans-Track-Vdata
git push origin --delete First-Branch-Trans-Track-Vdata
```