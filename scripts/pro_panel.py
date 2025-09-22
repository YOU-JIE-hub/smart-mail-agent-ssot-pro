import pathlib, matplotlib.pyplot as plt, matplotlib.image as mpimg
root=pathlib.Path("."); out=(root/"reports_auto/pro/latest")
cm_i=out/"cm_intent.png"; cm_s=out/"cm_spam.png"; rel=out/"reliability_spam.png"
imgs=[]
for p in [cm_i, cm_s, rel]:
    imgs.append(mpimg.imread(p) if p.exists() else None)

fig=plt.figure(figsize=(10,8))
titles=["Intent 混淆矩陣","Spam 混淆矩陣","Spam 可靠度"]
pos=[(2,2,1),(2,2,2),(2,1,2)]  # 前兩張 2x2，第三張佔整列
for i,(im,ttl,sp) in enumerate(zip(imgs,titles,pos)):
    ax=fig.add_subplot(*sp)
    if im is None:
        ax.text(0.5,0.5,"(missing)",ha="center",va="center")
        ax.axis("off")
    else:
        ax.imshow(im)
        ax.axis("off")
    ax.set_title(ttl)
fig.tight_layout()
(fig.savefig(out/"summary_panel.png", dpi=160))
print("[OK] panel:", out/"summary_panel.png")
