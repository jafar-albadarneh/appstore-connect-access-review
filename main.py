import streamlit as st
import pandas as pd
import json
import re

# Page configuration
st.set_page_config(
    page_title="App Store Connect Access Review", 
    layout="wide",
    page_icon="🛡️"
)

# --- Helper functions for parsing iOS roles and capabilities
def parse_ios_roles(roles_list):
    """Parse iOS roles list into a readable format"""
    if not roles_list or roles_list == 'None':
        return []
    return [role.strip().upper() for role in roles_list if role.strip()]

def format_ios_roles_for_display(roles):
    """Format iOS roles list for better readability"""
    if not roles:
        return "None"
    return ', '.join(roles)

def get_visible_apps_count(visible_apps_data):
    """Extract the total number of visible apps from the API response"""
    if not visible_apps_data or 'meta' not in visible_apps_data:
        return 0
    return visible_apps_data.get('meta', {}).get('paging', {}).get('total', 0)

def prepare_export_data(df):
    """Prepare data for export with all analysis columns"""
    export_df = df.copy()
    # Convert roles list to string for CSV export
    export_df['Roles_String'] = export_df['Parsed_Roles'].apply(lambda x: ', '.join(x) if x else 'None')
    export_columns = {
        'Email': 'Email',
        'FirstName': 'First Name',
        'LastName': 'Last Name',
        'Username': 'Username',
        'UserID': 'User ID',
        'Roles_String': 'Roles',
        'Roles Count': 'Roles Count',
        'allAppsVisible': 'All Apps Visible',
        'provisioningAllowed': 'Provisioning Allowed',
        'emailVettingRequired': 'Email Vetting Required',
        'VisibleAppsCount': 'Visible Apps Count',
    }
    export_df = export_df[list(export_columns.keys())].rename(columns=export_columns)
    return export_df

# Initialize dangerous iOS roles in session state
def initialize_dangerous_ios_roles():
    if 'dangerous_ios_roles' not in st.session_state:
        # Default to Security Focused preset for iOS
        st.session_state.dangerous_ios_roles = {
            "ADMIN",
            "ACCOUNT_HOLDER", 
            "APP_MANAGER",
            "CLOUD_MANAGED_APP_DISTRIBUTION",
            "GENERATE_INDIVIDUAL_KEYS",
            "ACCESS_TO_REPORTS"
        }

def get_dangerous_ios_roles():
    initialize_dangerous_ios_roles()
    return st.session_state.dangerous_ios_roles

def has_dangerous_ios_role(user_roles):
    dangerous_roles = get_dangerous_ios_roles()
    for role in user_roles:
        if role in dangerous_roles:
            return True
    return False

def analyze_ios_user(row):
    reasons = []
    if row['allAppsVisible']:
        reasons.append('Can see all apps')
    if row['provisioningAllowed']:
        reasons.append('Can manage certificates/provisioning')
    if has_dangerous_ios_role(row['Parsed_Roles']):
        reasons.append('Has dangerous roles')
    return ', '.join(reasons) if reasons else 'Normal'

def load_and_process_ios_data(uploaded_file):
    """Load and process the uploaded iOS JSON file"""
    try:
        data = json.load(uploaded_file)
        users_data = data.get('data', [])
        
        # Convert to DataFrame
        processed_users = []
        for user in users_data:
            attributes = user.get('attributes', {})
            relationships = user.get('relationships', {})
            
            processed_user = {
                'Email': attributes.get('email', ''),
                'Username': attributes.get('username', ''),
                'FirstName': attributes.get('firstName', ''),
                'LastName': attributes.get('lastName', ''),
                'Roles': attributes.get('roles', []),
                'allAppsVisible': attributes.get('allAppsVisible', False),
                'provisioningAllowed': attributes.get('provisioningAllowed', False),
                'emailVettingRequired': attributes.get('emailVettingRequired', False),
                'UserID': user.get('id', '')
            }
            
            # Get visible apps count
            visible_apps = relationships.get('visibleApps', {})
            processed_user['VisibleAppsCount'] = get_visible_apps_count(visible_apps)
            
            processed_users.append(processed_user)
        
        df = pd.DataFrame(processed_users)
        
        # Parse roles for better display
        df['Parsed_Roles'] = df['Roles'].apply(parse_ios_roles)
        
        # Create readable summary columns
        df['Roles Count'] = df['Parsed_Roles'].apply(len)
        df['Access Review'] = df.apply(analyze_ios_user, axis=1)
        
        # Always recalculate dangerous_users using the current dangerous_ios_roles from settings
        # Use dangerous_users for the table and expanders
        # The exporter/export_df should always export the full user list (df), not dangerous_users
        dangerous_roles = set([r.upper() for r in st.session_state.dangerous_ios_roles])
        dangerous_users = df[df['Parsed_Roles'].apply(lambda roles: any(role.upper() in dangerous_roles for role in roles))].copy().reset_index(drop=True)
        
        return df
    except Exception as e:
        st.error(f"Error processing JSON file: {str(e)}")
        return None

def reprocess_ios_analysis():
    if 'df' in st.session_state:
        st.session_state.df['Access Review'] = st.session_state.df.apply(analyze_ios_user, axis=1)

# Place this at the top level, with other helpers

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🛡️ App Store Connect Access Review")
st.sidebar.markdown("---")
st.sidebar.text("Analyze App Store Connect user roles for security risks. Upload your JSON export to get started.")

# Initialize dangerous iOS roles (always available)
initialize_dangerous_ios_roles()

# Only show Home and Settings in sidebar
if st.sidebar.button("🏠 Home", use_container_width=True):
    st.session_state.current_page = "Welcome"
    st.rerun()
if st.sidebar.button("⚙️ Settings", use_container_width=True):
    st.session_state.current_page = "Settings"
    st.rerun()

# Minimal Home page
if 'current_page' not in st.session_state or st.session_state.current_page == "Welcome":
    st.session_state.current_page = "Welcome"
    st.title("🛡️ App Store Connect Access Review Tool")
    
    with st.expander("How to get your App Store Connect users export", expanded=False):
        st.markdown("""
        ### How to Export Your App Store Connect Users List
        1. Open **App Store Connect** in your browser
        2. Go to **Users and Access** section
        3. Open Developer Tools (F12) and go to Network tab
        4. Navigate to the users page and look for the API call to:
           ```
           https://appstoreconnect.apple.com/iris/v1/users?include=visibleApps,provider&limit=500&sort=lastName&limit[visibleApps]=3&fields[apps]=&fields[users]=allAppsVisible,email,emailVettingRequired,firstName,lastName,provider,provisioningAllowed,roles,username,visibleApps
           ```
        5. Copy the response and save it as a JSON file
        6. Upload the JSON file here
        """)
    
    uploaded_file = st.file_uploader("📁 Upload JSON file", type=["json"])
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        # Process data and store in session state
        if 'df' not in st.session_state or st.session_state.get('uploaded_file_name') != uploaded_file.name:
            st.session_state.df = load_and_process_ios_data(uploaded_file)
            st.session_state.uploaded_file_name = uploaded_file.name
            if st.session_state.df is not None:
                st.rerun()
    
    if 'df' in st.session_state and st.session_state.df is not None:
        df = st.session_state.df
        # --- Inline Risk Analysis Results ---
        st.markdown("---")
        st.header("🚨 Account Risk Analysis")
        
        # === iOS ORGANIZATIONAL TAKEOVER ROLES ===
        IOS_ORG_TAKEOVER_ROLES = {
            'ADMIN',
            'ACCOUNT_HOLDER',
        }
        
        def has_account_level_access(user_roles):
            admin_account_roles = set(p.replace(' ', '').upper() for p in st.session_state.dangerous_ios_roles)
            for role in user_roles:
                role_norm = role.replace(' ', '').upper()
                for admin_role in admin_account_roles:
                    if admin_role in role_norm:
                        return True
            return False
        
        def has_org_takeover_role(user_roles):
            org_takeover_roles = set(p.replace(' ', '').upper() for p in IOS_ORG_TAKEOVER_ROLES)
            for role in user_roles:
                role_norm = role.replace(' ', '').upper()
                if any(org_role in role_norm for org_role in org_takeover_roles):
                    return True
            return False
        
        dangerous_roles = set([r.upper() for r in st.session_state.dangerous_ios_roles])
        dangerous_users = df[df['Parsed_Roles'].apply(lambda roles: any(role.upper() in dangerous_roles for role in roles))].copy().reset_index(drop=True)
        
        # --- BADGE SUMMARY UI ---
        from streamlit.components.v1 import html
        
        # Collect user lists
        critical_users = dangerous_users
        all_apps_visible_users = df[df['allAppsVisible'] == True]
        provisioning_users = df[df['provisioningAllowed'] == True]
        
        # Badge style helper
        badge_css = """
        <style>
        .badge-row {{display: flex; gap: 1.5rem; margin-bottom: 1.5rem;}}
        .badge {{
          display: inline-flex; align-items: center; font-size: 1.1rem; font-weight: 600;
          border-radius: 2em; padding: 0.5em 1.2em; margin-right: 0.5em; margin-bottom: 0.2em;
          color: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        }}
        .badge.critical {{background: #e74c3c;}}
        .badge.apps {{background: #f39c12;}}
        .badge.prov {{background: #2980b9;}}
        .badge .count {{margin-left: 0.5em; font-size: 1.2em; font-weight: bold;}}
        </style>
        <div class="badge-row">
          <div class="badge critical">🔴 Critical <span class="count">{critical_count}</span></div>
          <div class="badge apps">⚠️ All Apps Visible <span class="count">{apps_count}</span></div>
          <div class="badge prov">🔧 Provisioning <span class="count">{prov_count}</span></div>
        </div>
        """.format(
            critical_count=len(critical_users),
            apps_count=len(all_apps_visible_users),
            prov_count=len(provisioning_users)
        )
        html(badge_css, height=60)
        
        # Expanders for user lists
        with st.expander(f"🔴 Critical Users ({len(critical_users)})"):
            st.write(", ".join(critical_users['Email'].tolist()) if not critical_users.empty else "None")
        with st.expander(f"⚠️ All Apps Visible Users ({len(all_apps_visible_users)})"):
            st.write(", ".join(all_apps_visible_users['Email'].tolist()) if not all_apps_visible_users.empty else "None")
        with st.expander(f"🔧 Provisioning Users ({len(provisioning_users)})"):
            st.write(", ".join(provisioning_users['Email'].tolist()) if not provisioning_users.empty else "None")
        
        # --- END BADGE SUMMARY ---
        
        st.subheader("🚨 Risk Assessment")
        display_df = dangerous_users[['Email', 'allAppsVisible', 'provisioningAllowed']].copy()
        display_df = display_df.rename(columns={
            'allAppsVisible': '🔍 All Apps',
            'provisioningAllowed': '🔧 Provisioning'
        })
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # User-by-user expander section
        st.subheader('🔍 Inspect Users with Potentially Dangerous Roles')
        for idx, user in dangerous_users.iterrows():
            with st.expander(user['Email']):
                role_tags = [
                    f"<span style='background:#e74c3c;color:#fff;padding:2px 10px;border-radius:1em;margin-right:4px;font-size:1em;'>🔴 {role}</span>"
                    for role in user['Parsed_Roles'] if role.upper() in dangerous_roles
                ]
                if role_tags:
                    st.markdown(' '.join(role_tags), unsafe_allow_html=True)
                else:
                    st.markdown('*No Potentially Dangerous Roles*', unsafe_allow_html=True)
        
        # Export functionality
        st.markdown("---")
        st.subheader("📤 Export Data")
        
        # Exporter/export_df should always export the full user list (df)
        export_df = prepare_export_data(df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Export all users
            csv_all = export_df.to_csv(index=False)
            st.download_button(
                label="📁 Export All Users (CSV)",
                data=csv_all,
                file_name=f"appstore_connect_users_all_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                help="Download all users with risk analysis as CSV"
            )
        
        with col2:
            # Export currently filtered users
            if 'filtered_export_data' in st.session_state and st.session_state.filtered_export_data is not None:
                csv_filtered = st.session_state.filtered_export_data.to_csv(index=False)
                st.download_button(
                    label=f"📊 Export Filtered ({st.session_state.filtered_export_count} users)",
                    data=csv_filtered,
                    file_name=f"appstore_connect_users_filtered_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    help="Download filtered users based on selected risk levels"
                )
            else:
                pass
        
        # Show export summary
        st.info(f"📋 **Export Summary**: {len(export_df)} total users, {len(dangerous_users)} users with dangerous roles")

elif 'current_page' in st.session_state and st.session_state.current_page == "Settings":
    st.title("⚙️ Settings")
    st.markdown("""
    ### What are these settings for?
    
    This tool monitors **dangerous iOS roles** that could allow account risk or organizational takeover if compromised. 
    The settings control which roles are flagged as high-risk during your access review.
    """)
    
    # Define preset configurations for iOS
    presets = {
        "🔒 Security Focused": {
            "ADMIN",
            "ACCOUNT_HOLDER", 
            "APP_MANAGER",
        },
        "Custom": None,  # Will be detected if current roles don't match any preset
        "📊 Financial Focus": {
            'ACCESS_TO_REPORTS', 'FINANCE', 'MARKETING', 'SALES'
        },
        "🔄 Legacy Default": {
            'ADMIN', 'ACCOUNT_HOLDER', 'APP_MANAGER', 'CLOUD_MANAGED_APP_DISTRIBUTION',
            'GENERATE_INDIVIDUAL_KEYS', 'ACCESS_TO_REPORTS', 'FINANCE'
        }
    }
    
    # Detect current preset
    current_roles = st.session_state.dangerous_ios_roles
    current_preset = "Custom"
    for preset_name, preset_roles in presets.items():
        if preset_roles is not None and preset_roles == current_roles:
            current_preset = preset_name
            break
    
    preset_names = list(presets.keys())
    current_index = preset_names.index(current_preset) if current_preset in preset_names else 0
    
    st.markdown("### Preset")
    selected_preset = st.selectbox(
        "Choose a preset:",
        preset_names,
        index=current_index,
        help="Select a security configuration or use Custom to edit manually"
    )
    
    if selected_preset != current_preset and selected_preset != "Custom":
        st.session_state.dangerous_ios_roles = presets[selected_preset].copy()
        if 'df' in st.session_state:
            reprocess_ios_analysis()
        st.success(f"Applied {selected_preset} preset")
        st.rerun()
    
    st.markdown("### Active Roles")
    dangerous_roles = st.session_state.dangerous_ios_roles.copy()
    st.caption(f"Currently monitoring {len(dangerous_roles)} roles.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        if dangerous_roles:
            roles_to_remove = []
            for i, role in enumerate(sorted(dangerous_roles)):
                col_role, col_btn = st.columns([5, 1])
                with col_role:
                    st.write(f"• {role}")
                with col_btn:
                    if st.button("❌", key=f"remove_{i}", help=f"Remove {role}"):
                        roles_to_remove.append(role)
            for role in roles_to_remove:
                st.session_state.dangerous_ios_roles.discard(role)
                if 'df' in st.session_state:
                    reprocess_ios_analysis()
                st.rerun()
        else:
            st.info("No roles currently being monitored.")
    
    with col2:
        new_role = st.text_input("Add role:", placeholder="e.g., DEVELOPER")
        if st.button("Add", key="add_role_btn"):
            if new_role and new_role.strip():
                st.session_state.dangerous_ios_roles.add(new_role.strip().upper())
                if 'df' in st.session_state:
                    reprocess_ios_analysis()
                st.success(f"Added: {new_role.strip().upper()}")
                st.rerun()
            else:
                st.error("Please enter a valid role name")
        
        if st.button("Reset to Preset", key="reset_preset_btn"):
            if selected_preset != "Custom" and presets[selected_preset]:
                st.session_state.dangerous_ios_roles = presets[selected_preset].copy()
                if 'df' in st.session_state:
                    reprocess_ios_analysis()
                st.success(f"Reset to {selected_preset}")
                st.rerun()
    
    with st.expander("Export / Import Roles", expanded=False):
        current_roles_list = list(st.session_state.dangerous_ios_roles)
        roles_json = json.dumps(current_roles_list, indent=2)
        st.download_button(
            "Export Roles as JSON",
            data=roles_json,
            file_name=f"ios_roles_{selected_preset.replace(' ', '_').lower()}.json",
            mime="application/json",
        )
        uploaded_roles = st.file_uploader("Import Roles JSON", type=["json"])
        if uploaded_roles is not None:
            try:
                imported_roles = json.load(uploaded_roles)
                if isinstance(imported_roles, list):
                    st.session_state.dangerous_ios_roles = set(imported_roles)
                    if 'df' in st.session_state:
                        reprocess_ios_analysis()
                    st.success(f"Imported {len(imported_roles)} roles")
                    st.rerun()
                else:
                    st.error("Invalid JSON format. Expected a list of roles.")
            except json.JSONDecodeError:
                st.error("Invalid JSON file.")

st.sidebar.markdown("---")
st.sidebar.caption("🛡️ Built for App Store Connect access governance")