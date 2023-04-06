import toml
import os
import sys
from git import Repo

current_dir = os.path.dirname(os.path.realpath(__file__))
toml_file = os.path.join(current_dir, "radar")

def clone_and_checkout(repo_url, local_path):
	if os.path.exists(local_path):
		repo = Repo(local_path)
		repo.git.fetch()
		# check if local branch exists
		if 'develop' not in repo.heads:
			repo.git.checkout('origin/develop', b='develop')
		repo.git.checkout('develop')
		repo.git.pull()
		return repo.git.rev_parse('HEAD')
	repo = Repo.clone_from(repo_url, local_path)
	repo.git.checkout('origin/develop', b='develop')
	return repo.git.rev_parse('HEAD')

def parse_toml(toml_file):
	toml_content = {}
	with open(toml_file, 'r') as f:
		toml_content = toml.load(f)
	return toml_content

class RadarProject:
	new_commit: str = None
	local_path: str = None
	def __init__(self, repo, name, commit):
		self.repo = repo
		self.name = name
		self.commit = commit

def projects_from_toml(toml_file):
	radar = parse_toml(toml_file)
	git_base_url = radar.get('git_base_url')
	projects = []
	for repo in radar['proj_list']:
		repo_name = radar[repo].get('git_name') or repo
		if git_base_url:
			url = f"{git_base_url}/{repo_name}"
		else:
			url = radar[repo]['git_url']
		projects.append(RadarProject(url, repo_name, radar[repo]['commit']))
	return projects


def create_checkouts_dir():
	checkouts_dir = os.path.join(current_dir, "libs")
	if not os.path.exists(checkouts_dir):
		os.mkdir(checkouts_dir)
	return checkouts_dir

def reset_deps_files():
	settings_deps_file = os.path.join(current_dir, "internal_dependencies.gradle")
	open(settings_deps_file, 'w').close()
	for project in projects:
		gradle_dependencies_file = os.path.join(project.local_path, "internal_dependencies.gradle")
		open(gradle_dependencies_file, 'w').close()

def change_dependencies_to_local_sources(project_list):
	for project in project_list:
		with open(os.path.join(current_dir, "internal_dependencies.gradle"), 'a') as f:
			f.write(f"include ':libs:{project.name}'\n")

		dependencies_file = os.path.join(project.local_path, "dependencies")
		if not os.path.exists(dependencies_file):
			continue
		with open(dependencies_file, 'r') as f:
			# split file by new line
			dependencies = f.read().splitlines()
		with open(os.path.join(project.local_path, "internal_dependencies.gradle"), 'w') as f:
			f.write("dependencies {\n")
			for dependency in dependencies:
				f.write(f"\timplementation project(':libs:{dependency}')\n")
			f.write("}\n")

def append_publish_to_gradle_file(project_list):
	for project in project_list:
		gradle_dependencies_file = os.path.join(project.local_path, "internal_dependencies.gradle")
		with open(gradle_dependencies_file, 'a') as f:
			f.write(f"""
apply plugin: 'maven-publish'

afterEvaluate {{
    publishing {{
        publications {{
            release(MavenPublication) {{
                from components.release
                groupId "com.example"
                artifactId "{project.name}"
                version = "{project.new_commit}"
            }}
        }}
    }}
}}
""")

def publish_gradle_libs(project_list):
	for project in project_list:
		if os.system(f"cd {project.local_path} && ./gradlew publishToMavenLocal") != 0:
			return 1
	return 0

def update_radar_file(project_list):
	for project in project_list:
		radar = parse_toml(toml_file)
		radar['proj_list'][project.name]['commit'] = project.new_commit
		with open(toml_file, 'w') as f:
			toml.dump(radar, f)

def update_dependencies_commit():
	project_list = projects_from_toml(toml_file)
	radar = parse_toml(toml_file)

	for project in project_list:
		dependencies_file = os.path.join(project.local_path, "dependencies")
		if not os.path.exists(dependencies_file):
			continue
		with open(dependencies_file, 'r') as f:
			# split file by new line
			dependencies = f.read().splitlines()
		gradle_dependencies_file = os.path.join(project.local_path, "internal_dependencies.gradle")
		with open(gradle_dependencies_file, 'w') as f:
			f.write("dependencies {\n")
			for dependency in dependencies:
				commit = radar[dependency]['commit']
				f.write(f"\timplementation 'com.example:{dependency}:{commit}'\n")
			f.write("}\n")

if __name__ == "2__main__":
	reset_deps_files()
	update_dependencies_commit()


if __name__ == "__main__":
	projects = projects_from_toml(toml_file)
	checkouts = create_checkouts_dir()
	for project in projects:
		path = os.path.join(checkouts, project.name)
		project.new_commit = clone_and_checkout(project.repo, path)
		project.local_path = path
	reset_deps_files()
	change_dependencies_to_local_sources(projects)
	append_publish_to_gradle_file(projects)
	if publish_gradle_libs(projects) == 0:
		update_radar_file(projects)

