import streamlit as st
from database import SessionLocal
from models import User

st.set_page_config(page_title="管理后台", layout="wide")
st.title("用户管理后台")

db = SessionLocal()

try:
    users = db.query(User).order_by(User.id.desc()).all()
    total = len(users)
    active = sum(1 for u in users if u.is_active)

    col1, col2, col3 = st.columns(3)
    col1.metric("总用户数", total)
    col2.metric("活跃用户", active)
    col3.metric("不活跃", total - active)

    st.divider()
    st.subheader("用户列表")

    if users:
        rows = [
            {
                "ID": u.id,
                "用户名": u.username,
                "邮箱": u.email,
                "API Key": u.api_key[:16] + "..." if u.api_key else "-",
                "活跃": "是" if u.is_active else "否",
                "注册时间": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-",
            }
            for u in users
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("暂无用户数据")

finally:
    db.close()
