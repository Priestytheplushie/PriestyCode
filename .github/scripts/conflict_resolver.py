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

def parse_hunk_header(hunk_line):
    """Parse a hunk header line like '@@ -1,4 +1,6 @@' to extract line numbers."""
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', hunk_line)
    if match:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
        return old_start, old_count, new_start, new_count
    return None, None, None, None

def parse_conflicts_with_context(file_path, patch_content):
    """
    Parses conflict markers and maps them to patch positions more reliably.
    """
    conflicts = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = [line.rstrip('\n') for line in f.readlines()]
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return []

    if not patch_content:
        return []

    patch_lines = patch_content.splitlines()
    
    # Parse conflicts from file
    in_conflict = False
    is_ours_section = True
    current_conflict = {}
    
    for file_line_idx, file_line in enumerate(file_lines):
        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            current_conflict = {
                'ours': [],
                'theirs': [],
                'start_line': file_line_idx,
                'patch_position': -1
            }
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            in_conflict = False
            
            # Find patch position by looking for the content in the patch
            found_position = False
            
            # Look for any line from the "ours" section in the patch
            for ours_line in current_conflict['ours']:
                if ours_line.strip():  # Skip empty lines
                    for patch_idx, patch_line in enumerate(patch_lines):
                        if patch_line.startswith('+') and patch_line[1:].strip() == ours_line.strip():
                            current_conflict['patch_position'] = patch_idx
                            found_position = True
                            break
                    if found_position:
                        break
            
            # If not found in "ours", try "theirs" section
            if not found_position:
                for theirs_line in current_conflict['theirs']:
                    if theirs_line.strip():  # Skip empty lines
                        for patch_idx, patch_line in enumerate(patch_lines):
                            if patch_line.startswith('+') and patch_line[1:].strip() == theirs_line.strip():
                                current_conflict['patch_position'] = patch_idx
                                found_position = True
                                break
                        if found_position:
                            break
            
            if not found_position:
                print(f"Warning: Could not map conflict at line {file_line_idx} in {file_path} to patch position")
            
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

            # This is the actual raw conflict content that should be in the diff block
            raw_conflict_markers_content = textwrap.dedent(f"""
                <<<<<<< HEAD (Your changes from `{HEAD_BRANCH}`)
                {ours_body}
                =======
                {theirs_body}
                >>>>>>> {BASE_BRANCH} (Incoming changes from `{BASE_BRANCH}`)
            """).strip()

            # Now, wrap ONLY this content in a markdown diff code block
            formatted_raw_diff_block = f"```diff\n{raw_conflict_markers_content}\n```"

            # Create conflict details as plain text (NOT in code blocks)
            conflict_details_text = textwrap.dedent(f"""
                **File:** `{conflict['file']}`
                **Your Branch (`{HEAD_BRANCH}`):** Changes you're trying to merge.
                **Base Branch (`{BASE_BRANCH}`):** Branch you are merging into.
            """).strip()

            # Construct the full conflict details block within <details>
            conflict_details_block = f"""<details>
<summary>👉 Click to review conflict details</summary>

### Merge Conflict Details
{conflict_details_text}

### Raw Conflict Block
This is how the conflict is marked in the file. Git needs you to choose one version.

**Legend:**
- `<<<<<<< HEAD` - Start of your changes (from `{HEAD_BRANCH}`)
- `=======` - Separator between conflicting versions
- `>>>>>>> {BASE_BRANCH}` - End marker with incoming changes

{formatted_raw_diff_block}
</details>"""
            
            # Construct the comment body with sections in the desired order
            comment_body_parts = []
            
            comment_body_parts.append(textwrap.dedent(f"""
                ### ✨ Heads up! A merge conflict was detected here.

                It looks like this spot was changed in both your branch (`{HEAD_BRANCH}`) and the base branch (`{BASE_BRANCH}`). Please choose which version to keep.

                **Recommendation:** Consider "Option 1: Keep Your Changes" if your version introduces a new feature or fix that should be integrated. Choose "Option 2: Use Incoming Changes" if the base branch's update is more critical or resolves a conflict you don't need to address in your branch. You also have "Option 3: Manual Intervention" if you prefer to resolve the conflict yourself using the GitHub web editor or command line.
            """).strip())

            # Add Option 1
            if ours_body.strip():
                comment_body_parts.append(textwrap.dedent(f"""
                    ### 🔵 Option 1: Keep Your Changes (from `{HEAD_BRANCH}`)
                    Select this option if your changes are the correct version to resolve this conflict.
                    ```suggestion
                    {ours_body}
                    ```
                """).strip())
            
            # Add Option 2
            if theirs_body.strip():
                comment_body_parts.append(textwrap.dedent(f"""
                    ### 🟢 Option 2: Use Incoming Changes (from `{BASE_BRANCH}`)
                    Select this option if the incoming changes from the base branch are what's needed here.
                    ```suggestion
                    {theirs_body}
                    ```
                """).strip())

            # Add Option 3: Manual Intervention (new section, always visible)
            comment_body_parts.append(textwrap.dedent(f"""
                ### 🟠 Option 3: Manual Intervention
                If neither of the above options fully resolves the conflict, or if you prefer to handle it yourself, you can use these methods:
                * **GitHub Web Editor:** Click the **[Resolve conflicts button]({pr.html_url}/conflicts)** in the GitHub web interface for a guided visual editor.
                * **Command Line:** Resolve locally by pulling changes and editing the files in your preferred code editor.
                    ```bash
                    git fetch origin
                    git checkout {HEAD_BRANCH}
                    git merge origin/{BASE_BRANCH}
                    # After merging, your files will contain conflict markers (<<<<<<<, =======, >>>>>>>).
                    # Open the conflicted files in your code editor, manually resolve the differences,
                    # and remove the conflict markers.
                    git add .
                    git commit -m "Resolve merge conflicts"
                    git push
                    ```
            """).strip())

            # Add the conflict details block last, but still within the main comment body
            comment_body_parts.append(conflict_details_block)

            comment_body = "\n\n".join(comment_body_parts) # Join with double newlines for separation
            
            review_comments.append({
                "path": conflict['file'],
                "position": conflict['patch_position'],
                "body": comment_body
            })

        if not review_comments:
            print("All conflicts resulted in empty suggestions. Nothing to post.")
            set_github_output("status", "no_actionable_conflicts")
            return

        # Create the review summary (this part remains largely the same)
        summary_body_parts = []
        summary_body_parts.append(textwrap.dedent(f"""
            {BOT_REVIEW_HTML_COMMENT}
            
            Hey team! 👋 {BOT_USERNAME} here to help.

            I was getting this branch ready to merge and ran into **{len(mappable_conflicts)} merge conflict(s)** between your branch (`{HEAD_BRANCH}`) and `{BASE_BRANCH}`.

            No worries, this is a normal part of collaborating. Here are a few ways we can get this sorted:
            1. **Use My Suggestions (Easiest):** For most conflicts, you can simply head to the **[Files changed tab]({pr.html_url}/files)** and click the **"Commit suggestion"** button on the comments I've left. This will automatically apply the suggested change to your branch and create a new commit.
            2. **Use the GitHub Web Editor:** If a conflict needs a custom fix, the **[Resolve conflicts button]({pr.html_url}/conflicts)** is your best friend.
        """).strip())

        # New to Merge Conflicts section (moved to top)
        summary_body_parts.append(textwrap.dedent(f"""
            <details>
            <summary>🤔 New to Merge Conflicts? Learn More Here!</summary>
            
            Merge conflicts happen when the same lines of code are changed in different ways on different branches. They're a normal part of collaborative development and nothing to worry about!
            
            **What causes merge conflicts?**
            - Two people edit the same line of code differently
            - One person edits a line while another person deletes it
            - Complex changes that Git can't automatically merge
            
            **How to resolve them:**
            1. **Use the suggestions above** - I've analyzed the conflicts and provided quick-fix buttons (which use "Commit suggestion" to apply changes).
            2. **Use GitHub's web editor** - Click the "Resolve conflicts" button for a visual editor
            3. **Use your local editor** - Pull the changes locally and edit the files manually
            </details>
        """).strip())

        # Command Line section (now collapsible and not shown by default)
        summary_body_parts.append(textwrap.dedent(f"""
            <details>
            <summary>🚀 Command Line Instructions</summary>
            
            ### Conflicted Files
            ```
            {chr(10).join([f"- {c['file']}" for c in mappable_conflicts])}
            ```
            
            ### Resolve with the Command Line (Full Control)
            For advanced users who prefer local resolution:
            ```bash
            git fetch origin
            git checkout {HEAD_BRANCH}
            git merge origin/{BASE_BRANCH}
            # After merging, your files will contain conflict markers (<<<<<<<, =======, >>>>>>>).
            # Open the conflicted files in your code editor, manually resolve the differences,
            # and remove the conflict markers.
            git add .
            git commit -m "Resolve merge conflicts"
            git push
            ```
            </details>
            
            Let me know if you get stuck. Let's get this PR merged! 🚀
        """).strip())

        summary_body = "\n\n".join(summary_body_parts) # Join with double newlines for separation
        
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