import streamlit as st
import git
import shutil
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
import datetime
import os
import vars
import yaml
import pandas as pd
import errno
from cfg_converter import convertToCfg
import markdown

def extract_features_from_pom(file_path):
    features = set()


    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Define the XML namespace for Maven POM
        namespace = {'ns': 'http://maven.apache.org/POM/4.0.0'}

        # Find all dependencies in the POM file
        dependencies = root.findall('.//ns:dependencies/ns:dependency', namespace)

        parent_element = root.find('ns:parent', namespace)
        if parent_element is not None:
            vars.current_springboot_version = parent_element.find('ns:version', namespace).text
        
        for dependency in dependencies:
            # Extract the groupId and artifactId for each dependency
            group_id = dependency.find('ns:groupId', namespace).text
            artifact_id = dependency.find('ns:artifactId', namespace).text

            # Concatenate groupId and artifactId to represent a feature
            feature = f'{group_id}:{artifact_id}'
            features.add(feature)

    except ET.ParseError as e:
        print(f"Error parsing {file_path}: {e}")
        st.error(f"Error parsing {file_path}: {e}")
    
    return features

def clone_repo(url, branch_name, foldername):
    try:
        repo = git.Repo.clone_from(url, foldername, branch=branch_name )
        st.session_state.working_dir = repo.working_dir
        print(f"Successfully cloned repository")
    except git.GitCommandError as e:
        print(f"Error cloning repository: {e}")
        st.error(f"Error cloning repository: {e}")
    
    pom_file = "./" + foldername + "/pom.xml"

    vars.features_used_full_list = extract_features_from_pom(pom_file)
    analyse_existing_deps()

def push_folder_to_branch(repo_path, source_branch, target_branch):

    repo = git.Repo(repo_path)

    # Check if the branch exists
    if any(branch.name == target_branch for branch in repo.branches):
        # If the branch exists, checkout to it
        repo.git.checkout(target_branch)
    else:
        # If the branch doesn't exist, create and checkout to it
        repo.git.checkout(source_branch)  # Checkout the base branch (e.g., 'master')
        repo.git.checkout('-b', target_branch)  # Create and switch to the new branch

    repo.git.add("--all")

    # Commit changes
    repo.index.commit("Commiting changes for rosa")

    # Push changes to the branch
    repo.git.push("origin", target_branch)
    print(f"Changes pushed to target branch successfully")
    st.success("Changes pushed to "+target_branch+" branch in your git repo")

def delete_local_folder(folder_path, max_retries=3, wait_time=5):
    attempts = 0
    while attempts < max_retries:
        try:
            shutil.rmtree(folder_path)
            print(f"Folder '{folder_path}' deleted successfully.")
            return True
        except Exception as e:
            print(f"Error occurred while deleting folder: {e}")
            print("Retrying...")
            attempts += 1
            time.sleep(wait_time)
    print(f"Unable to delete folder '{folder_path}' after {max_retries} attempts.")
    return False

def remove_all_except_git(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if '.git' not in file_path:
                os.remove(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if '.git' not in dir_path:
                shutil.rmtree(dir_path)

def add_values_to_key(file_path1, file_path2, key_to_update, new_file_name):
    try:
        # Load YAML content from both files
        with open(file_path1, 'r') as f1, open(file_path2, 'r') as f2:
            yaml1 = yaml.safe_load(f1)
            yaml2 = yaml.safe_load(f2)

        if key_to_update in yaml1 and key_to_update in yaml2:
            # Add values of the key from the second file to the first file
            yaml1[key_to_update] += yaml2[key_to_update]

            # Save the updated content to a new YAML file
            with open(new_file_name, 'w') as outfile:
                yaml.dump(yaml1, outfile, default_flow_style=False)

            print(f"Updated content saved to '{new_file_name}'")
            return new_file_name
        else:
            st.error("Key not found in both files or one of the files.")
            return None

    except FileNotFoundError:
        st.error("File not found.")
        return None
    except yaml.YAMLError as e:
        st.error(f"Error parsing YAML: {e}")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def analyse_existing_deps():
    if vars.features_used_full_list:
        print("Features used in the Spring Boot application:")
        for feature in vars.features_used_full_list:
            vars.found_features.add("Spring boot version")
            if feature in vars.feature_lookup:
                vars.found_features.add(vars.feature_lookup[feature])
    else:
        print("No features found in the POM file.")
    
    build_feature_list_df()

def build_feature_list_df():
    vars.feature_list_df = pd.DataFrame.from_dict( {
            "Feature": list(vars.feature_lookup.values()),
            "Status": [
                "FOUND" if feature in vars.found_features else "NOT FOUND"
                for feature in vars.feature_lookup.values()
            ],
        }
    )

def delete_specific_class_files(directory, filenames):
    """Deletes specified Java class files from a directory and its subdirectories.

    Args:
        directory (str): The directory path to search.
        filenames (list): A list of file names to delete with extensions.
    """
    print("in the delete function: ", directory, filenames)
    try:
        for root, directories, files in os.walk(directory):
            for file in filenames:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Deleted class file: {file_path}")
                    # else:
                    #     print(f"File Not Found: {file_path}")
        print("#########Deleteion Complete######")
    except OSError as e:
        if e.errno == errno.ENOENT:
            print(f"Directory not found: {directory}")
        else:
            print(f"Error accessing directory: {directory} ({e})")

def find_folder_path(directory, target_folder):
    for root, dirs, files in os.walk(directory):
        if target_folder in dirs:
            return os.path.join(root, target_folder)

def move_file(source_path, destination_directory, filename):
    try:
        # Construct the new path for the file in the destination directory
        new_file_path = os.path.join(destination_directory, filename)

        # Use shutil.move() to move the file
        shutil.move(source_path, new_file_path)
        print(f"File moved from {source_path} to {new_file_path}")
    except shutil.Error as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

st.set_page_config(page_title="PCF to ROSA", layout="wide", menu_items={
    'Get Help': None,
    'Report a bug': None,
    'About': None
})

st.markdown("""
    <style>
    .block-container {
        padding-top: 0rem;
    }
    .main {
       font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; align: center;
    }
    h1 {
        color: #ff6347;
        text-align: center;
    }
    
    h5 {
        text-align: center;
        font-size:30px;
    }
    .font {
        font-size:16px;
        font-weight: 400;
    }            

    </style>
    """, unsafe_allow_html=True)


st.markdown("# PCF to ROSA")
foldername = f"data_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}";
col1, col2 = st.columns([1,2])

with col1:
    with st.expander("**Analyze your AB3 application:**", expanded=True):
        # Form with input box and submit button
        with st.form(key='analyze_form', clear_on_submit=False):
            gitrepo_url = st.text_input(
                label="Start with your gitlab url. Make sure to add the <<bot id>> to your git repo", value="https://github.ibm.com/psudhakar-ibm/sample-pcf-app.git"
            )    

            gitrepo_branch = st.text_input(
                label="Source Branch", value="main"
            )

            submit_button = st.form_submit_button(label="**Analyze PCF/AB3 Application**", type="primary")

            if submit_button:
                with st.spinner("Processing..."):
                    url = gitrepo_url.strip()
                    st.session_state.url = url
                    st.session_state.gitrepo_branch = gitrepo_branch
                    if not gitrepo_url or not gitrepo_branch:
                         st.error("Please fill in URL, Source Branch and Target Branch fields.")
                    else:
                        # Check if URL is empty
                        if not url:
                            st.error("Please provide a valid GitLab URL")    
                        else:
                            try:
                                # Clone the repository using the provided URL
                                # foldername = f"data_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                                st.session_state.foldername = f"data_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                                clone_repo(url, gitrepo_branch, st.session_state.foldername)
                            except Exception as e:
                                st.error(f"Unexpected error occurred: {e}")            

with col2:
    with st.expander("**Existing Integrations:**", expanded=True):
        if (vars.feature_list_df.empty):
            st.write("Analzye a AB3 application to see its existing integrations and dependencies!")            
        else:
            st.markdown("Spring boot version: " + vars.current_springboot_version)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.dataframe(vars.feature_list_df[0:5])
            with col2:
                st.dataframe(vars.feature_list_df[5:10])
            with col3:
                st.dataframe(vars.feature_list_df[10:15])


with st.expander("**Migration Options:**", expanded=True):
    if (vars.feature_list_df.empty):
        st.write("Analzye a AB3 application and then pick migration options ")            
    else:        
        with st.form(key='migration_form', clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                target_authn_framework = st.radio("Which Identity Management Framework you want to use?", ("Continue using abcd(OpenAM)", "Migrate to Azure AD(Entra ID)", "Use Both abcd and Azure AD"))
                target_java_version = st.radio("Pick a Java version for target application: ", ("Keep as-is", "Java 17"))
            with col2:
                target_secrets_storage_option = st.radio("Where do you want to store your application Secrets?", ("Continue to use Vault", "Use AWS Secrets Manager(ASM)", "Use both Vault and ASM"))
                target_springboot_version   = st.radio("Do you want to upgrade to latest Spring boot version?", ("Keep as-is", "Migrate to latest vrsion of Spring boot 2", "Migrate to latest vrsion of Spring boot 3"))
            with col3:
                st.markdown("**Select your cleanup options**")
                target_cleanup_vault = st.checkbox("Cleanup the vault related dependencies and config")
                target_cleanup_connectors = st.checkbox("Cleanup Cloudfoundry Connectors")
                target_cleanup_abcd = st.checkbox("Cleanup abcd related dependencies and config")
                # cfgStatus = st.checkbox("Convert property files to configMap.yml")
                # st.markdown("Note: Please move all of your property files into root of your project repo before clicking submit.")

            inputNames = st.text_area("Enter the filenames, including extension, that you would like to clean-up separated by commas:")
            st.markdown("**Convert property files to configMap.yml**")
            st.markdown("Note: Please move all of your property files into one folder in your project repo.")
            inputFolder = st.text_input(label = "Folder Name:", value="property_files")
            submit_button = st.form_submit_button(label="**Begin migration**", type="primary")

            if submit_button:
                with st.spinner("Processing..."):
                    add_values_to_key("rewrite-manifestCleanup.yml","rewrite-postgresConnectorCleanup.yml","recipeList", "merged.yml")
                    add_values_to_key("merged.yml","rewrite-springCloudPcfCleanup.yml","recipeList", "merged.yml")
                    text_markdown_file = "\n\nCleaning manisfest files, Postgres connectors, Spring cloud PCF libraries"

                    if target_authn_framework == "Continue using abcd(OpenAM)":
                        pass #Nothing to do
                    elif target_authn_framework == "Migrate to Azure AD(Entra ID)":
                        add_values_to_key("merged.yml","rewrite-azureAD.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\nadding azure AD related libraries"
                        #need to add java class creation and properties config file creation
                    else:
                        add_values_to_key("merged.yml","rewrite-azureAD.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\nadding azure AD related libraries"
                        #need to add java class creation and properties config file creation

                    if target_java_version == "Keep as-is":
                        pass # nothing to do
                    else:
                        add_values_to_key("merged.yml","rewrite-java17.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\nrewriting to java 17"

                    if target_secrets_storage_option == "Continue to use Vault":
                        pass #nothing to do
                    elif target_secrets_storage_option == "Use AWS Secrets Manager(ASM)":
                        pass #nothing to do
                    else:
                        pass #nothing to do

                    if target_springboot_version == "Keep as-is":
                        pass #nothing to do
                    elif target_springboot_version == "Migrate to latest vrsion of Spring boot 2":
                        pass # Add recipe to migrate to latest version of Spring boot 2
                    else:
                        pass # Add recipe to migrate to latest version of Spring boot 3

                    if target_cleanup_vault:
                        add_values_to_key("merged.yml","rewrite-vaultCleanup.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\ncleaning up vault"
                    if target_cleanup_connectors:
                        add_values_to_key("merged.yml","rewrite-redisAB3Cleanup.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\ncleaning redisAB3 related libraries"
                    if target_cleanup_abcd:
                        add_values_to_key("merged.yml","rewrite-abcdCleanup.yml","recipeList", "merged.yml")
                        text_markdown_file = text_markdown_file + "\ncleaning tcps libraries"
                    if inputNames:
                        filenames = inputNames.split(",")
                        file_path = os.path.join(os.getcwd(), st.session_state.foldername)
                        print("path where the files need to be deleted: ",file_path )
                        # filenames = ["sampleDelete.java","PetClinicConfiguration.java"]
                        delete_specific_class_files(file_path,filenames)
                        text_markdown_file = text_markdown_file + "\ndeleted files : "+inputNames
                    if inputFolder:
                        dir = os.path.join(os.getcwd(), st.session_state.foldername)
                        inputPath = find_folder_path(dir, inputFolder)
                        print(f"Path to the file: {inputPath}")
                        convertToCfg(inputPath)

                    destination_path = os.path.join(st.session_state.foldername, 'rewrite.yml')
                    shutil.copyfile('merged.yml', destination_path)
                    current_directory = st.session_state.working_dir
                    os.chdir(st.session_state.foldername)

                    command = ["mvn -U org.openrewrite.maven:rewrite-maven-plugin:run -Drewrite.activeRecipes=com.ibm.pcf2rosa > execution.log"]
                    os.system(" ".join(command))
                    source_path = os.path.abspath('execution.log')
                    current_file_path = os.path.abspath(__file__)
                    executionLogPath = os.path.dirname(current_file_path)
                    fileName = st.session_state.foldername + "execution.log"
                    move_file(source_path, executionLogPath, fileName)
                    # Convert the DataFrame to Markdown
                    markdown_table = vars.feature_list_df.to_markdown(index=False)

                    with open("pcf2rosa_changes.md", "w") as file:
                        file.write("Following are the features of your application.\n\nSpring boot version: " + vars.current_springboot_version+"\n\n"+markdown_table+text_markdown_file)

                    push_folder_to_branch(st.session_state.working_dir, st.session_state.gitrepo_branch, f"pcf2rosa_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
                    remove_command = ["git rm --cached *"]
                    os.system(" ".join(remove_command))
                    os.chdir(current_directory)
                    remove_all_except_git(st.session_state.foldername)
                    st.success("Process completed successfully")

                
