import os
import sys
import subprocess # no
import re
from github import Github, GithubException #type: ignore
import textwrap

try:
    GH_TOKEN = os.environ["GH_TOKEN"]
    REPO_NAME = os.environ["REPO_NAME"]
    PR_NUMBER_STR = os.environ["PR_NUMBER"]
    BASE_BRANCH = os.environ["BASE_BRANCH"]
    HEAD_BRANCH = os.environ["HEAD_BRANCH"]
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "PriestyBot")
    BOT_REVIEW_TAG_RAW = os.environ.get("BOT_REVIEW_TAG_RAW", "BOT_REVIEW_TAG")
    BOT_REVIEW_HTML_COMMENT = f"<!-- {BOT_REVIEW_TAG_RAW} -->"
except KeyError as e:
    print(f"Error: Missing required environment variable: {e}", file=sys.stderr)
    sys.exit(1)

PR_NUMBER = int(PR_NUMBER_STR)
g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(PR_NUMBER)

# --- Helper Functions ---
def set_github_output(name, value):
    """Sets a GitHub Actions output using the modern environment file method."""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"Warning: GITHUB_OUTPUT not set. Simulating output: {name}={value}")

def run_command(command):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        print(f"STDOUT: {result.stdout.strip()}")
        print(f"STDERR: {result.stderr.strip()}")
    return result.stdout, result.stderr, result.returncode

def dismiss_stale_reviews():
    print("Checking for stale reviews to dismiss...")
    try:
        reviews = pr.get_reviews()
        for review in reviews:
            if review.user.login == BOT_USERNAME and review.state == "CHANGES_REQUESTED" and BOT_REVIEW_HTML_COMMENT in review.body:
                print(f"Dismissing stale PriestyBot review {review.id}...")
                review.dismiss("New conflict resolution in progress or conflicts resolved.")
    except GithubException as e:
        print(f"Warning: Could not dismiss reviews, continuing. Error: {e}")

def get_hunk_info(patch_lines):
    hunks = []
    for i, line in enumerate(patch_lines):
        if line.startswith('@@'):
            hunks.append({'hunk_header_idx': i})
    return hunks

# --- NEW, MORE ROBUST PARSER ---
def parse_conflicts_with_context(file_path, patch_content):
    """
    Parses conflict markers using context lines to robustly map the conflict
    to the correct position in the PR's diff.
    """
    conflicts = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = [line.rstrip('\n') for line in f.readlines()]
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return []

    patch_lines = patch_content.splitlines() if patch_content else []
    hunks = get_hunk_info(patch_lines)
    
    in_conflict = False
    is_ours_section = True
    current_conflict = {}
    CONTEXT_LINES = 2 # Number of stable lines to use as an anchor

    for i, file_line in enumerate(file_lines):
        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            context = [line for line in file_lines[max(0, i - CONTEXT_LINES):i]]
            current_conflict = {'ours': [], 'theirs': [], 'context': context, 'patch_position': -1}
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            in_conflict = False
            
            # Find the position in the patch
            found_position = False
            if current_conflict['context']:
                 for hunk in hunks:
                    hunk_start_idx = hunk['hunk_header_idx']
                    # Search within the lines of this specific hunk
                    for patch_idx in range(hunk_start_idx + 1, len(patch_lines)):
                        # Look for the context anchor
                        is_context_match = True
                        for ctx_idx, ctx_line in enumerate(current_conflict['context']):
                            current_patch_line_idx = patch_idx + ctx_idx
                            if not (current_patch_line_idx < len(patch_lines) and \
                                    patch_lines[current_patch_line_idx].startswith(' ') and \
                                    patch_lines[current_patch_line_idx][1:] == ctx_line):
                                is_context_match = False
                                break
                        
                        if is_context_match:
                            # Context found, now check if the 'ours' lines follow
                            ours_start_in_patch = patch_idx + len(current_conflict['context'])
                            is_ours_match = True
                            for ours_idx, ours_line in enumerate(current_conflict['ours']):
                                current_patch_line_idx = ours_start_in_patch + ours_idx
                                if not (current_patch_line_idx < len(patch_lines) and \
                                        patch_lines[current_patch_line_idx].startswith('+') and \
                                        patch_lines[current_patch_line_idx][1:] == ours_line):
                                    is_ours_match = False
                                    break
                            
                            if is_ours_match:
                                # Position is relative to the hunk header!
                                current_conflict['patch_position'] = ours_start_in_patch - hunk_start_idx
                                found_position = True
                                break
                    if found_position:
                        break

            if not found_position:
                 print(f"Warning: Could not map conflict in {file_path} to patch lines using context. Skipping inline comment.")

            conflicts.append(current_conflict)
        elif in_conflict:
            if is_ours_section:
                current_conflict['ours'].append(file_line)
            else:
                current_conflict['theirs'].append(file_line)
    
    return conflicts

# --- Main Bot Logic ---
def main():
    try:
        print(f"Starting conflict resolution for PR #{PR_NUMBER}...")
        run_command(f'git config user.name "{BOT_USERNAME}"')
        run_command(f'git config user.email "{BOT_USERNAME}@users.noreply.github.com"')
        run_command("git fetch origin --prune")
        run_command(f"git checkout {BASE_BRANCH} && git pull origin {BASE_BRANCH}")
        run_command(f"git checkout {HEAD_BRANCH}")
        dismiss_stale_reviews()

        print(f"Attempting merge of 'origin/{BASE_BRANCH}' into '{HEAD_BRANCH}'...")
        _, _, returncode = run_command(f"git merge origin/{BASE_BRANCH} --no-commit --no-ff")
        
        if returncode == 0:
            print("✅ No merge conflicts found.")
            run_command("git merge --abort")
            set_github_output("status", "no_conflicts")
            return

        print("❌ Merge conflicts detected. Parsing details...")
        stdout, _, _ = run_command("git diff --name-only --diff-filter=U")
        conflicted_files_list = [f for f in stdout.split('\n') if f]
        
        pr_files = pr.get_files()
        pr_file_patches = {f.filename: f.patch for f in pr_files if f.patch}
        
        all_parsed_conflicts = []
        for file_path in conflicted_files_list:
            patch_content = pr_file_patches.get(file_path)
            if not patch_content:
                print(f"Warning: Could not find patch content for '{file_path}'.")
                continue
            # Use the new robust parser
            parsed_for_file = parse_conflicts_with_context(file_path, patch_content)
            all_parsed_conflicts.extend({'file': file_path, **p} for p in parsed_for_file)

        run_command("git merge --abort")

        mappable_conflicts = [c for c in all_parsed_conflicts if c.get('patch_position', -1) != -1]
        
        if not mappable_conflicts:
            print("Could not map any conflicts to specific diff lines. Posting a fallback comment.")
            
            # Create a fallback comment when conflicts can't be mapped
            fallback_files_list = '\n'.join([f'- `{f}`' for f in conflicted_files_list])
            fallback_comment = textwrap.dedent(f"""
                {BOT_REVIEW_HTML_COMMENT}
                
                Hey team! 👋 {BOT_USERNAME} here to help.
                
                I detected **{len(conflicted_files_list)} conflicted file(s)** between your branch (`{HEAD_BRANCH}`) and `{BASE_BRANCH}`, but I couldn't map them to specific lines in the diff.
                
                **Files with conflicts:**
                {fallback_files_list}
                
                **How to resolve:**
                1. Use the **[Resolve conflicts button]({pr.html_url}/conflicts)** in the GitHub web interface
                2. Or resolve locally using the command line:
                   ```bash
                   git fetch origin
                   git checkout {HEAD_BRANCH}
                   git merge origin/{BASE_BRANCH}
                   # Fix conflicts in your editor
                   git add .
                   git commit -m "Resolve merge conflicts"
                   git push
                   ```
                
                Let me know if you need help! 🚀
            """).strip()
            
            pr.create_issue_comment(fallback_comment)
            set_github_output("status", "conflicts_posted_fallback")
            return

        review_comments = []
        for conflict in mappable_conflicts:
            ours_body = '\n'.join(conflict['ours'])
            theirs_body = '\n'.join(conflict['theirs'])

            # Skip creating suggestions for empty code blocks
            if not ours_body.strip() and not theirs_body.strip():
                continue

            conflict_details_block = textwrap.dedent(f"""
                <details>
                <summary>👉 Click to view the conflict and resolution options</summary>

                #### Merge Conflict Details
                * **File:** `{conflict['file']}`
                * **Your Branch (`{HEAD_BRANCH}`):** The changes you're trying to merge.
                * **Base Branch (`{BASE_BRANCH}`):** The branch you are merging into.

                #### Raw Conflict Block
                This is how the conflict is marked in the file. Git needs you to choose one version.

                ```diff
                <<<<<<< HEAD (Your changes from `{HEAD_BRANCH}`)
                {ours_body}
                =======
                {theirs_body}
                >>>>>>> {BASE_BRANCH} (Incoming changes from `{BASE_BRANCH}`)
                ```
                </details>
            """).strip()
            
            # Option 1: Always offer 'ours' as a suggestion now that mapping is reliable
            option_1_text = ""
            if ours_body.strip():
                option_1_text = textwrap.dedent(f"""
                    ---
                    #### 🔵 Option 1: Keep Your Changes (from `{HEAD_BRANCH}`)
                    If your version is the correct one to resolve the conflict, click the button below.
                    ```suggestion
                    {ours_body}
                    ```
                """).strip()
            
            # Option 2: 'theirs'
            option_2_text = ""
            if theirs_body.strip():
                option_2_text = textwrap.dedent(f"""
                    ---
                    #### 🟢 Option 2: Use Incoming Changes (from `{BASE_BRANCH}`)
                    If the code from the base branch is what we need, click the button below. I'll apply the change for you.
                    ```suggestion
                    {theirs_body}
                    ```
                """).strip()

            comment_body = textwrap.dedent(f"""
                #### ✨ Heads up! A merge conflict was detected here.
                It looks like this spot was changed in both your branch (`{HEAD_BRANCH}`) and the base branch (`{BASE_BRANCH}`). Please choose which version to keep.

                {conflict_details_block}
                {option_1_text}
                {option_2_text}
            """).strip()
            
            review_comments.append({
                "path": conflict['file'],
                "position": conflict['patch_position'],
                "body": comment_body
            })

        if not review_comments:
            print("All conflicts resulted in empty suggestions. Nothing to post.")
            set_github_output("status", "no_actionable_conflicts")
            return

        # Create the review summary
        summary_body = textwrap.dedent(f"""
            {BOT_REVIEW_HTML_COMMENT}
            
            Hey team! 👋 {BOT_USERNAME} here to help.

            I was getting this branch ready to merge and ran into **{len(mappable_conflicts)} merge conflict(s)** between your branch (`{HEAD_BRANCH}`) and `{BASE_BRANCH}`.

            No worries, this is a normal part of collaborating. Here are a few ways we can get this sorted:
            1. **Use My Suggestions (Easiest):** For most conflicts, you can simply head to the **[Files changed tab]({pr.html_url}/files)** and click the suggestion button on the comments I've left.
            2. **Use the GitHub Web Editor:** If a conflict needs a custom fix, the **[Resolve conflicts button]({pr.html_url}/conflicts)** is your best friend.
            
            ---
            Let me know if you get stuck. Let's get this PR merged! 🚀
        """).strip()
        
        print(f"Submitting 'Changes Requested' review with {len(review_comments)} comments...")
        pr.create_review(body=summary_body, event="REQUEST_CHANGES", comments=review_comments)
        print("✅ Review submitted successfully.")
        set_github_output("status", "conflicts_posted")

    except GithubException as e:
        print(f"An error occurred with the GitHub API: {e}", file=sys.stderr)
        
        error_comment = textwrap.dedent(f"""
            {BOT_REVIEW_HTML_COMMENT}
            
            ❌ Oops! {BOT_USERNAME} ran into a problem interacting with GitHub.
            
            Hey team, my apologies! I encountered an error while trying to post the conflict resolution review. This often means there was an issue with how I tried to suggest changes (e.g., trying to comment on a line that no longer exists in the PR's current diff).
            
            **What you can do:**
            1. Check the **[Files changed tab]({pr.html_url}/files)** to see if there are any existing conflict markers
            2. Use the **[Resolve conflicts button]({pr.html_url}/conflicts)** to resolve conflicts manually
            3. Or resolve locally with: `git merge origin/{BASE_BRANCH}` and fix conflicts in your editor
            
            ---
            
            **Technical details for maintainers:**
            ```
            {str(e)}
            ```
        """).strip()
        
        try:
            pr.create_issue_comment(error_comment)
        except Exception as comment_error:
            print(f"Could not post error comment: {comment_error}", file=sys.stderr)
        
        set_github_output("status", "error")
        sys.exit(1)
        
    except Exception as e:
        print(f"An unexpected general error occurred: {e}", file=sys.stderr)
        
        error_comment = textwrap.dedent(f"""
            {BOT_REVIEW_HTML_COMMENT}
            
            ❌ Oops! {BOT_USERNAME} encountered an unexpected error.
            
            Hey team, my apologies! Something went wrong while I was analyzing the merge conflicts. 
            
            **What you can do:**
            1. Try using the **[Resolve conflicts button]({pr.html_url}/conflicts)** to resolve conflicts manually
            2. Or resolve locally with: `git merge origin/{BASE_BRANCH}` and fix conflicts in your editor
            
            ---
            
            **Technical details for maintainers:**
            ```
            {str(e)}
            ```
        """).strip()
        
        try:
            pr.create_issue_comment(error_comment)
        except Exception as comment_error:
            print(f"Could not post error comment: {comment_error}", file=sys.stderr)
        
        set_github_output("status", "error")
        sys.exit(1)

if __name__ == "__main__":
    main()