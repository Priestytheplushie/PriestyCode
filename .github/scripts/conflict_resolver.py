import os
import sys
import subprocess
import re
from github import Github, GithubException
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

def get_conflict_type(file_path):
    """Determine the type of conflict for a file."""
    stdout, _, _ = run_command(f"git status --porcelain {file_path}")
    if stdout.strip().startswith("AA"):
        return "add/add"
    elif stdout.strip().startswith("UU"):
        return "modify/modify"
    else:
        return "unknown"

def get_hunk_info(patch_lines):
    """Extract hunk headers and their start/end line numbers within the patch."""
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

def parse_conflicts(file_path, patch_content):
    """Parse conflict markers and map them to PR diff lines."""
    conflicts = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = f.readlines()
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return []

    # Check conflict type
    conflict_type = get_conflict_type(file_path)
    print(f"DEBUG: Conflict type for {file_path}: {conflict_type}")

    # For add/add conflicts, we need special handling
    if conflict_type == "add/add":
        return parse_add_add_conflicts(file_path, file_lines, patch_content)
    else:
        return parse_modify_conflicts(file_path, file_lines, patch_content)

def parse_add_add_conflicts(file_path, file_lines, patch_content):
    """Handle add/add conflicts where both branches created the same file."""
    conflicts = []
    
    # For add/add conflicts, we'll create a general conflict without specific patch positioning
    # since the file didn't exist in the base branch
    
    in_conflict = False
    is_ours_section = True
    current_conflict = {}
    
    for i, file_line in enumerate(file_lines):
        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            current_conflict = {
                'ours': [], 
                'theirs': [], 
                'patch_position': -1,  # Will be handled specially for add/add
                'original_pr_lines': [], 
                'start_marker': file_line.strip(), 
                'end_marker': '',
                'conflict_type': 'add/add'
            }
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            in_conflict = False
            current_conflict['end_marker'] = file_line.strip()
            current_conflict['ours'] = [l.rstrip('\n') for l in current_conflict['ours']]
            current_conflict['theirs'] = [l.rstrip('\n') for l in current_conflict['theirs']]
            
            # For add/add conflicts, we'll use a different approach
            # Try to find the position in the patch if it exists
            if patch_content:
                patch_lines = patch_content.splitlines()
                # Look for the content in the patch
                for j, patch_line in enumerate(patch_lines):
                    if patch_line.startswith('+') and current_conflict['ours']:
                        if patch_line[1:].strip() == current_conflict['ours'][0].strip():
                            current_conflict['patch_position'] = j
                            break
            
            conflicts.append(current_conflict)
        elif in_conflict:
            if is_ours_section:
                current_conflict['ours'].append(file_line)
            else:
                current_conflict['theirs'].append(file_line)
    
    return conflicts

def parse_modify_conflicts(file_path, file_lines, patch_content):
    """Handle modify/modify conflicts using the original logic."""
    conflicts = []
    
    if not patch_content:
        return conflicts
        
    patch_lines = patch_content.splitlines()
    hunks = get_hunk_info(patch_lines)

    in_conflict = False
    is_ours_section = True
    current_conflict = {}
    
    for i, file_line in enumerate(file_lines):
        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            current_conflict = {
                'ours': [], 
                'theirs': [], 
                'patch_position': -1, 
                'original_pr_lines': [], 
                'start_marker': file_line.strip(), 
                'end_marker': '',
                'conflict_type': 'modify/modify'
            }
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            in_conflict = False
            current_conflict['end_marker'] = file_line.strip()
            current_conflict['ours'] = [l.rstrip('\n') for l in current_conflict['ours']]
            current_conflict['theirs'] = [l.rstrip('\n') for l in current_conflict['theirs']]

            # Try to map to patch position
            found_position = False
            if current_conflict['ours']:
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
                print(f"Warning: Could not map conflict in {file_path} to patch lines.")
            
            conflicts.append(current_conflict)
        elif in_conflict:
            if is_ours_section:
                current_conflict['ours'].append(file_line)
            else:
                current_conflict['theirs'].append(file_line)
    
    return conflicts

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
        
        print(f"DEBUG: Found {len(conflicted_files_list)} conflicted files: {conflicted_files_list}")
        
        pr_files = pr.get_files()
        pr_file_patches = {f.filename: f.patch for f in pr_files if f.patch}
        
        print(f"DEBUG: PR has {len(pr_file_patches)} files with patches")
        
        all_parsed_conflicts = []
        for file_path in conflicted_files_list:
            patch_content = pr_file_patches.get(file_path)
            print(f"DEBUG: Processing {file_path}, has patch: {patch_content is not None}")
            
            parsed_for_file = parse_conflicts(file_path, patch_content)
            all_parsed_conflicts.extend({'file': file_path, **p} for p in parsed_for_file)

        run_command("git merge --abort")

        # Handle conflicts differently based on whether they can be mapped to patch lines
        mappable_conflicts = [c for c in all_parsed_conflicts if c['patch_position'] != -1]
        add_add_conflicts = [c for c in all_parsed_conflicts if c.get('conflict_type') == 'add/add']
        
        print(f"DEBUG: Mappable conflicts: {len(mappable_conflicts)}")
        print(f"DEBUG: Add/add conflicts: {len(add_add_conflicts)}")
        
        if not mappable_conflicts and not add_add_conflicts:
            print("Could not parse any conflicts. Posting a fallback comment.")
            fallback_body = textwrap.dedent(f"""\
                {BOT_REVIEW_HTML_COMMENT}
                ### ⚠️ {BOT_USERNAME} detected a Merge Conflict
                Hey team! I found {len(conflicted_files_list)} file(s) with conflicts, but I couldn't generate specific suggestions. 
                
                **Conflicted Files:**
                ```
                {chr(10).join(conflicted_files_list)}
                ```
                
                Please use the **[Resolve conflicts button]({pr.html_url}/conflicts)** above to resolve these conflicts.
            """)
            pr.create_issue_comment(fallback_body)
            set_github_output("status", "error_no_suggestions")
            return

        # Handle add/add conflicts with general comments
        if add_add_conflicts:
            for conflict in add_add_conflicts:
                ours_body = '\n'.join(conflict['ours'])
                theirs_body = '\n'.join(conflict['theirs'])

                raw_conflict_block = f"""```diff
{conflict['start_marker']}
{ours_body}
=======
{theirs_body}
{conflict['end_marker']}
```"""

                add_add_comment = textwrap.dedent(f"""\
                    {BOT_REVIEW_HTML_COMMENT}
                    ### 💥 Add/Add Merge Conflict in `{conflict['file']}`
                    
                    Both your branch (`{HEAD_BRANCH}`) and the base branch (`{BASE_BRANCH}`) created the file `{conflict['file']}` with different content.
                    
                    <details>
                    <summary><strong>Conflict Details</strong></summary>
                    {raw_conflict_block}
                    </details>
                    
                    **Your version (`{HEAD_BRANCH}`):**
                    ```
                    {ours_body}
                    ```
                    
                    **Base branch version (`{BASE_BRANCH}`):**
                    ```
                    {theirs_body}
                    ```
                    
                    Please use the **[Resolve conflicts button]({pr.html_url}/conflicts)** to choose which version to keep or merge them manually.
                """)
                
                pr.create_issue_comment(add_add_comment)

        # Handle mappable conflicts with inline comments (original logic)
        if mappable_conflicts:
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
                    comment_body = textwrap.dedent(f"""\
                        ### 💥 Merge Conflict Detected
                        Conflict in **`{conflict['file']}`** between `{HEAD_BRANCH}` and `{BASE_BRANCH}`.

                        <details>
                        <summary><strong>Visualize Raw Conflict</strong></summary>
                        {raw_conflict_block}
                        </details>

                        #### 🚀 **Use Version from `{BASE_BRANCH}`**
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
                    # Two separate comments for distinct changes
                    comment_body_ours = textwrap.dedent(f"""\
                        ### 💥 Merge Conflict: Option 1/2
                        #### ✅ **Keep Your Version** (from `{HEAD_BRANCH}`)
                        ```suggestion
                        {ours_body}
                        ```
                        """)
                    review_comments.append({
                        "path": conflict['file'],
                        "position": conflict['patch_position'],
                        "body": comment_body_ours
                    })

                    comment_body_theirs = textwrap.dedent(f"""\
                        ### 💥 Merge Conflict: Option 2/2
                        #### 🚀 **Use Version from `{BASE_BRANCH}`**
                        ```suggestion
                        {theirs_body}
                        ```
                        """)
                    review_comments.append({
                        "path": conflict['file'],
                        "position": conflict['patch_position'],
                        "body": comment_body_theirs
                    })

            if review_comments:
                summary_body = textwrap.dedent(f"""\
                    {BOT_REVIEW_HTML_COMMENT}
                    ### 🔀 Merge Conflicts Detected
                    Hey team! I found merge conflicts that need resolution. Check the **[Files changed tab]({pr.html_url}/files)** for my suggestions.
                    
                    Alternative: Use the **[Resolve conflicts button]({pr.html_url}/conflicts)** for manual resolution.
                """)
                pr.create_review(body=summary_body, event="REQUEST_CHANGES", comments=review_comments)

        set_github_output("status", "conflicts_posted")
        print("✅ Conflict resolution completed.")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        set_github_output("status", "error")
        try:
            error_comment = textwrap.dedent(f"""\
                {BOT_REVIEW_HTML_COMMENT}
                ### ❌ {BOT_USERNAME} Error
                I encountered an error while processing conflicts. Please resolve manually using the **[Resolve conflicts button]({pr.html_url}/conflicts)**.
                
                <details>
                <summary>Error Details</summary>
                
                ```
                {str(e)}
                ```
                </details>
            """)
            pr.create_issue_comment(error_comment)
        except:
            pass

if __name__ == "__main__":
    main()