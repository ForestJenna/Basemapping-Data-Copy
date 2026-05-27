# GitHub + Local Git Cheat Sheet

This cheat sheet uses your current repository as the example:

- Repository: `https://github.com/ForestJenna/General-Helpers.git`
- Local folder: `E:\2026_vtpk\LocalRepo`
- Example branch: `First-Branch-Trans-Track-Vdata`

## 1. Clone the Repository

Use the repository URL, not the GitHub web page URL with `/tree/main`.

Correct:

```bash
git clone https://github.com/ForestJenna/General-Helpers.git
```

Wrong:

```bash
git clone https://github.com/ForestJenna/General-Helpers/tree/main
```

If you want Git to create the local folder for you:

```bash
cd E:\2026_vtpk
git clone https://github.com/ForestJenna/General-Helpers.git LocalRepo
cd LocalRepo
```

If `LocalRepo` already exists and is empty, you can clone directly into it:

```bash
cd E:\2026_vtpk\LocalRepo
git clone https://github.com/ForestJenna/General-Helpers.git .
```

The final `.` means "clone into the current folder."

## 2. Check Where You Are

See your current branch:

```bash
git branch
```

See repo status:

```bash
git status
```

See the remote GitHub URL:

```bash
git remote -v
```

## 3. Start From `main`

Move to the main branch:

```bash
git switch main
```

Pull the latest changes from GitHub:

```bash
git pull origin main
```

## 4. Create a New Branch

Create and switch to a new working branch:

```bash
git switch -c First-Branch-Trans-Track-Vdata
```

Confirm you are on it:

```bash
git branch
```

## 5. Make Changes Locally

Edit files in VS Code, then check what changed:

```bash
git status
```

See the unstaged differences:

```bash
git diff
```

## 6. Stage Changes

Stage everything:

```bash
git add .
```

Stage one file only:

```bash
git add path\to\file.py
```

## 7. Commit Changes

Commit the staged work:

```bash
git commit -m "Describe your changes"
```

If Git says your name or email is missing, set it once:

```bash
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"
```

## 8. Push the Branch to GitHub

First push for a new branch:

```bash
git push -u origin First-Branch-Trans-Track-Vdata
```

Later pushes on the same branch:

```bash
git push
```

## 9. Bring Down New Changes Later

Update your current branch from GitHub:

```bash
git pull
```

If you want the latest `main` before starting another new branch:

```bash
git switch main
git pull origin main
git switch -c another-branch-name
```

## 10. Common Problems

### `fatal: not a git repository`

You are not inside the cloned repo folder.

Fix:

```bash
cd E:\2026_vtpk\LocalRepo
```

### `repository not found`

You are usually using the wrong URL. Use the `.git` repository URL, not the GitHub page URL.

### `nothing to commit, working tree clean`

There are no changed files to commit right now.

### `please complete authentication in your browser`

GitHub authentication is required. Finish the sign-in flow, then rerun the command.

## 11. Minimal Everyday Workflow

```bash
cd E:\2026_vtpk\LocalRepo
git switch main
git pull origin main
git switch -c my-new-branch
```

Make edits, then:

```bash
git add .
git commit -m "Describe the changes"
git push -u origin my-new-branch
```

## 12. Your Current Example

You already created this branch:

```bash
git switch -c First-Branch-Trans-Track-Vdata
```

So your next steps are:

```bash
git status
git add .
git commit -m "Describe your changes"
git push -u origin First-Branch-Trans-Track-Vdata
```

## Quick Rule to Remember

Clone once. Branch from `main`. Edit locally. Then run:

```bash
git add .
git commit -m "Describe your changes"
git push
```