import streamlit as st
import sys
import traceback

# Debug: Hiển thị Python version và sys path
st.write("🐍 Python version:", sys.version)
st.write("📁 Current working directory:", __file__ if '__file__' in globals() else "Unknown")

try:
    # Test basic imports
    st.write("Testing imports...")
    
    # Test 1: OpenAI
    try:
        from openai import OpenAI
        st.success("✅ OpenAI import successful")
    except Exception as e:
        st.error(f"❌ OpenAI import failed: {e}")
    
    # Test 2: Requests
    try:
        import requests
        st.success("✅ Requests import successful")
    except Exception as e:
        st.error(f"❌ Requests import failed: {e}")
    
    # Test 3: Basic modules
    try:
        import json
        from datetime import datetime
        import re
        import time
        import os
        st.success("✅ Standard library imports successful")
    except Exception as e:
        st.error(f"❌ Standard library import failed: {e}")
    
    # Test 4: File reading
    st.write("Testing file access...")
    
    files_to_check = [
        "01.system_trainning.txt",
        "02.assistant.txt", 
        "module_chatgpt.txt"
    ]
    
    for filename in files_to_check:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
                st.success(f"✅ {filename} readable ({len(content)} chars)")
        except FileNotFoundError:
            st.warning(f"⚠️ {filename} not found")
        except Exception as e:
            st.error(f"❌ {filename} error: {e}")
    
    # Test 5: Secrets
    st.write("Testing secrets...")
    
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if api_key:
            st.success(f"✅ OPENAI_API_KEY found (length: {len(api_key)})")
        else:
            st.error("❌ OPENAI_API_KEY not found in secrets")
    except Exception as e:
        st.error(f"❌ Secrets access failed: {e}")
    
    # Test 6: Session state
    st.write("Testing session state...")
    
    try:
        if "test_counter" not in st.session_state:
            st.session_state.test_counter = 0
        
        st.session_state.test_counter += 1
        st.success(f"✅ Session state working (counter: {st.session_state.test_counter})")
    except Exception as e:
        st.error(f"❌ Session state failed: {e}")
    
    # Test 7: Basic UI components
    st.write("Testing UI components...")
    
    try:
        st.title("🧪 Test Title")
        st.markdown("**Test markdown**")
        
        if st.button("Test Button"):
            st.success("Button clicked!")
        
        test_input = st.text_input("Test input")
        if test_input:
            st.write(f"Input received: {test_input}")
        
        st.success("✅ UI components working")
    except Exception as e:
        st.error(f"❌ UI components failed: {e}")
    
    # Summary
    st.markdown("---")
    st.markdown("## 📊 Debug Summary")
    st.info("🎯 If you see this message, basic Streamlit is working!")
    st.write("Check above for any ❌ errors that need fixing.")
    
    # Next steps
    st.markdown("## 🚀 Next Steps")
    st.markdown("""
    1. **If all tests pass**: The issue might be in the main app logic
    2. **If imports fail**: Check requirements.txt
    3. **If files not found**: Check if files are in the repo
    4. **If secrets fail**: Configure OPENAI_API_KEY in app settings
    """)

except Exception as e:
    st.error("💥 Critical error in debug script!")
    st.code(traceback.format_exc())
    st.markdown("**Full error details:**")
    st.write(str(e))

# Emergency contact info
st.markdown("---")
st.markdown("### 🆘 Emergency Debug Info")
st.write("If this debug page doesn't load, check Streamlit Cloud logs for Python errors.")