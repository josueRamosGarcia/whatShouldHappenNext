import streamlit as st

st.title('Qué debe pasar después')

if 'n' not in st.session_state:
    st.session_state.n = 0

if st.button('Sumar'):
    st.session_state.n += 1

st.write('Clics:', st.session_state.n)