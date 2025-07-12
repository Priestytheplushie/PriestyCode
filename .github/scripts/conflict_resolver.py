import os
import sys
import subprocess
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
    # Retrieve the raw tag value. Using '[BOT_REVIEW_TAG]' as default for consistency
    # with previous discussion regarding its use as a literal tag.
    BOT_REVIEW_TAG_RAW = os.environ.get("BOT_REVIEW_TAG_RAW", "BOT_REVIEW_TAG") # Use .get for graceful handling with a default
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
        # Fallback for local testing/debugging outside GitHub Actions, not for production
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
            # Check for bot's username and the specific HTML comment tag
            if review.user.login == BOT_USERNAME and review.state == "CHANGES_REQUESTED" and BOT_REVIEW_HTML_COMMENT in review.body:
                print(f"Dismissing stale PriestyBot review {review.id}...")
                review.dismiss("New conflict resolution in progress or conflicts resolved.")
    except GithubException as e:
        # Log the error but don't stop the workflow, as this is a cleanup step.
        print(f"Warning: Could not dismiss reviews, continuing. Error: {e}")

def get_hunk_info(patch_lines):
    """
    Parses patch lines to extract hunk headers and their start/end line numbers within the patch.
    Returns a list of (hunk_header_idx, old_start_line, old_line_count, new_start_line, new_line_count)
    """
    hunks = []
    for i, line in enumerate(patch_lines):
        if line.startswith('@@'):
            match = re.match(r'@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@', line)
            if match:
                old_start, old_count, new_start, new_count = map(lambda x: int(x) if x else 1,
                                                                 [match.group(1), match.group(3),
                                                                  match.group(4), match.group(6)])
                hunks.append({
                    'hunk_header_idx': i,
                    'old_start': old_start,
                    'old_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count
                })
    return hunks

# --- PARSER ---
def parse_conflicts(file_path, patch_content):
    """
    Parses conflict markers and attempts to map them to the PR's diff lines.
    Returns conflicts with 'patch_position' relative to the hunk header.
    """
    conflicts = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = f.readlines()
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return []

    patch_lines = patch_content.splitlines() if patch_content else []
    hunks = get_hunk_info(patch_lines)

    in_conflict = False
    is_ours_section = True
    current_conflict = {}
    
    for i, file_line in enumerate(file_lines):
        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            current_conflict = {'ours': [], 'theirs': [], 'patch_position': -1, 'original_pr_lines': [], 'start_marker': '', 'end_marker': ''}
            current_conflict['start_marker'] = file_line.strip()
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            in_conflict = False
            current_conflict['end_marker'] = file_line.strip()
            current_conflict['ours'] = [l.rstrip('\n') for l in current_conflict['ours']]
            current_conflict['theirs'] = [l.rstrip('\n') for l in current_conflict['theirs']]

            found_position = False
            if current_conflict['ours']: # Only proceed if 'ours' section has content
                for hunk in hunks:
                    hunk_header_idx = hunk['hunk_header_idx']
                    
                    for k in range(1, len(patch_lines) - hunk_header_idx):
                        patch_line_idx = hunk_header_idx + k
                        if patch_line_idx >= len(patch_lines):
                            break

                        patch_line_content = patch_lines[patch_line_idx]
                        if patch_line_content.startswith('+'):
                            if patch_line_content[1:].rstrip('\n') == current_conflict['ours'][0]:
                                match_len = 0
                                for ours_idx, ours_line in enumerate(current_conflict['ours']):
                                    if (patch_line_idx + ours_idx) < len(patch_lines) and \
                                       patch_lines[patch_line_idx + ours_idx].startswith('+') and \
                                       patch_lines[patch_line_idx + ours_idx][1:].rstrip('\n') == ours_line:
                                        match_len += 1
                                    else:
                                        break
                                
                                if match_len == len(current_conflict['ours']):
                                    current_conflict['patch_position'] = k
                                    current_conflict['original_pr_lines'] = [
                                        patch_lines[hunk_header_idx + k + i][1:]
                                        for i in range(len(current_conflict['ours']))
                                    ]
                                    found_position = True
                                    break
                    if found_position:
                        break

            if not found_position:
                print(f"Warning: Could not map conflict in {file_path} to patch lines. Skipping inline comment for this conflict.")
            
            conflicts.append(current_conflict)
        elif in_conflict:
            if is_ours_section:
                current_conflict['ours'].append(file_line)
            else:
                current_conflict['theirs'].append(file_line)
    
    return conflicts

# --- Main Bot Logic with Robust Control Flow ---
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
        merge_stdout, merge_stderr, returncode = run_command(f"git merge origin/{BASE_BRANCH} --no-commit --no-ff")
        
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
                print(f"Warning: Could not find patch content for '{file_path}'. This file might be binary or outside the PR scope.")
                continue
            parsed_for_file = parse_conflicts(file_path, patch_content)
            all_parsed_conflicts.extend({'file': file_path, **p} for p in parsed_for_file)

        run_command("git merge --abort")

        mappable_conflicts = [c for c in all_parsed_conflicts if c['patch_position'] != -1]
        
        if not mappable_conflicts:
            print("Could not map any conflicts to specific diff lines for inline comments. Posting a fallback comment.")
            fallback_body = textwrap.dedent(f"""\
                {BOT_REVIEW_HTML_COMMENT}
                ### ⚠️ {BOT_USERNAME} detected a Merge Conflict
                Hey team! I found {len(conflicted_files_list)} file(s) with conflicts, but I couldn't generate specific inline suggestions. This can happen with complex conflicts or changes to binary files.
                The best way to resolve this is with the **[Resolve conflicts button]({pr.html_url}/conflicts)** above or by following the command line instructions.
                **Conflicted Files:**
                ```
                {chr(10).join(conflicted_files_list) or "Could not determine specific files."}
                ```
            """)
            pr.create_issue_comment(fallback_body)
            set_github_output("status", "error_no_suggestions")
            return

        review_comments = []
        for conflict in mappable_conflicts:
            ours_body = '\n'.join(conflict['ours'])
            theirs_body = '\n'.join(conflict['theirs'])
            original_body_in_patch = '\n'.join(conflict['original_pr_lines'])

            raw_conflict_block = f"""```diff
{conflict['start_marker']}
{ours_body}
=======
{theirs_body}
{conflict['end_marker']}
```"""

            if ours_body.strip() == original_body_in_patch.strip():
                # Case 1: "Ours" is already in the PR diff. We can't suggest it. Post one comment with one suggestion for "theirs".
                comment_body = textwrap.dedent(f"""\
                    ### 💥 Merge Conflict Detected
                    I've found a conflict in **`{conflict['file']}`**. This spot was changed in both your branch (`{HEAD_BRANCH}`) and the base branch (`{BASE_BRANCH}`). Please choose the version to keep.

                    <details>
                    <summary><strong>Visualize Raw Conflict</strong></summary>
                    {raw_conflict_block}
                    </details>

                    ---

                    #### ✅ **Option 1: Keep Your Version** (from `{HEAD_BRANCH}`)
                    Your current code is already in this PR. If this is correct, you'll need to resolve this conflict manually, perhaps by incorporating changes from `{BASE_BRANCH}`.
                    > **Note:** I can't offer a suggestion button for this option because your code is already part of the pull request's proposed changes.

                    *Your Version:*
                    ```
                    {ours_body}
                    ```

                    ---

                    #### 🚀 **Option 2: Use Version from `{BASE_BRANCH}`**
                    If you'd prefer to use the code from `{BASE_BRANCH}`, click the button below to apply it.

                    ```suggestion
                    {theirs_body}
                    ```
                    """)
                review_comments.append({
                    "path": conflict['file'],
                    "position": conflict['patch_position'],
                    "body": comment_body
                })
            else:
                # Case 2: "Ours" and "Theirs" are both distinct changes. Post two separate, clearly labeled comments to offer two distinct suggestions.
                # Comment for "ours" suggestion
                comment_body_ours = textwrap.dedent(f"""\
                    ### 💥 Merge Conflict: Option 1/2
                    This is **Option 1** for the conflict in **`{conflict['file']}`**. See the comment below for Option 2.

                    <details>
                    <summary><strong>Visualize Raw Conflict</strong></summary>
                    {raw_conflict_block}
                    </details>

                    ---

                    #### ✅ **Keep Your Version** (from `{HEAD_BRANCH}`)
                    Click the button below to resolve the conflict using the version from your branch.

                    ```suggestion
                    {ours_body}
                    ```
                    """)
                review_comments.append({
                    "path": conflict['file'],
                    "position": conflict['patch_position'],
                    "body": comment_body_ours
                })

                # Comment for "theirs" suggestion
                comment_body_theirs = textwrap.dedent(f"""\
                    ### 💥 Merge Conflict: Option 2/2
                    This is **Option 2** for the conflict in **`{conflict['file']}`**.

                    <details>
                    <summary><strong>Visualize Raw Conflict</strong></summary>
                    {raw_conflict_block}
                    </details>

                    ---

                    #### 🚀 **Use Version from `{BASE_BRANCH}`**
                    Click the button below to resolve the conflict using the version from the base branch.

                    ```suggestion
                    {theirs_body}
                    ```
                    """)
                review_comments.append({
                    "path": conflict['file'],
                    "position": conflict['patch_position'],
                    "body": comment_body_theirs
                })

        summary_body = textwrap.dedent(f"""\
            {BOT_REVIEW_HTML_COMMENT}
            Hey team! 👋 {BOT_USERNAME} here to help.
            I was getting this branch ready to merge and ran into **{len(mappable_conflicts)} merge conflict(s)** between your branch (`{HEAD_BRANCH}`) and `{BASE_BRANCH}`.
            No worries, this is a normal part of collaborating. Here are a few ways we can get this sorted:
            1.  **Use My Suggestions (Easiest):** For most conflicts, you can simply head to the **[Files changed tab]({pr.html_url}/files)** and click the suggestion button on the comments I've left.
            2.  **Use the GitHub Web Editor:** If a conflict needs a custom fix, the **[Resolve conflicts button]({pr.html_url}/conflicts)** is your best friend.
            <details>
            <summary>👉 For a full list of files or to use the command line</summary>

            #### Conflicted Files
            ```
            {chr(10).join(conflicted_files_list)}
            ```
            #### Resolve with the Command Line (Full Control)
            ```shell
            git fetch origin
            git checkout {HEAD_BRANCH}
            git merge origin/{BASE_BRANCH}
            # (Fix conflicts in your editor)
            git add .
            git commit -m "fix: Resolve merge conflicts from {BASE_BRANCH}"
            git push
            ```
            </details>
            ---
            Let me know if you get stuck. Let's get this PR merged! 🚀
        """)

        print(f"Submitting 'Changes Requested' review with {len(review_comments)} comments...")
        pr.create_review(body=summary_body, event="REQUEST_CHANGES", comments=review_comments)
        print("✅ Review submitted successfully.")
        set_github_output("status", "conflicts_posted")

    except GithubException as e:
        print(f"An error occurred with the GitHub API: {e}", file=sys.stderr)
        set_github_output("status", "error")
        try:
            error_comment = textwrap.dedent(f"""\
                {BOT_REVIEW_HTML_COMMENT}
                ### ❌ Oops! {BOT_USERNAME} ran into a problem interacting with GitHub.
                Hey team, my apologies! I encountered an error while trying to post the conflict resolution review. This often means there was an issue with how I tried to suggest changes (e.g., trying to comment on a line that no longer exists in the PR's current diff).
                You'll need to resolve any conflicts manually for now. The **[Resolve conflicts button]({pr.html_url}/conflicts)** above is a great place to start.
                <details>
                <summary><strong>Error Details (for debugging)</strong></summary>
                
                ```json
                {e.data}
                ```
                </details>
            """)
            pr.create_issue_comment(error_comment)
        except Exception as comment_e:
            print(f"Failed to post general API error comment to PR: {comment_e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected general error occurred: {e}", file=sys.stderr)
        set_github_output("status", "error")
        try:
            error_comment = textwrap.dedent(f"""\
                {BOT_REVIEW_HTML_COMMENT}
                ### ❌ Oops! {BOT_USERNAME} ran into an unexpected problem.
                Hey team, my apologies! I encountered an unexpected error while trying to check for merge conflicts and couldn't finish the job.
                You'll need to resolve any conflicts manually for now. The **[Resolve conflicts button]({pr.html_url}/conflicts)** above is a great place to start.
                <details>
                <summary><strong>Error Details (for debugging)</strong></summary>
                
                ```
                {str(e)}
                ```
                </details>
            """)
            pr.create_issue_comment(error_comment)
        except Exception as comment_e:
            print(f"Failed to post final error comment to PR: {comment_e}", file=sys.stderr)

if __name__ == "__main__":
    main()