# Push to vikash232 (personal) from a machine using vikash624 (company) SSH key

## 1. Create an SSH key for your personal GitHub (vikash232)

Run in terminal (use your personal email for vikash232):

```bash
ssh-keygen -t ed25519 -C "your-personal-email@example.com" -f ~/.ssh/id_ed25519_vikash232 -N ""
```

## 2. Add the key to GitHub (vikash232 account)

1. Copy the public key:
   ```bash
   cat ~/.ssh/id_ed25519_vikash232.pub
   ```
2. Log in to GitHub as **vikash232**.
3. Go to **Settings → SSH and GPG keys → New SSH key**.
4. Paste the key, give it a name (e.g. "Mac personal"), Save.

## 3. Tell SSH to use this key for your personal repos

Create or edit `~/.ssh/config`:

```bash
# Company GitHub (default for github.com)
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519   # or whatever key vikash624 uses

# Personal GitHub (vikash232)
Host github-personal
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_vikash232
```

If you're not sure which key vikash624 uses, run `ls ~/.ssh/*.pub` and use that key for the first `IdentityFile`. The important part is the second block: `Host github-personal` and the vikash232 key.

## 4. Point this repo at your personal account and push

From the repo root:

```bash
git remote set-url origin git@github-personal:vikash232/twitter-automation.git
git push -u origin main
```

## 5. After first push: add secrets for the AI workflow

In **vikash232/twitter-automation** on GitHub:

1. **Settings → Secrets and variables → Actions**
2. **New repository secret** for each:
   - `GEMINI_API_KEY` — get at https://aistudio.google.com/apikey
   - `TWITTER_CONSUMER_KEY`
   - `TWITTER_CONSUMER_SECRET`
   - `TWITTER_ACCESS_TOKEN`
   - `TWITTER_ACCESS_TOKEN_SECRET`

3. **Actions → Tweet (AI) → Run workflow** to test.

Done. Future pushes: `git push` (remote is already set).
