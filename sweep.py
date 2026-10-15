"""Round 3: add crowd PRESSURE (repulsion). This is the missing physics.

Round 1-2 failed because agents were points that could stack without limit,
producing 24-60 p/m2 -- physically impossible (real crowds jam at ~6-8 p/m2).

Fix: agents feel a force away from high-density areas (down the density
gradient). This is a simplified 'social force' model, standard in crowd
simulation. Result: crowds spread laterally and QUEUE, instead of stacking.
"""
import numpy as np

def run(gap_w, spawn_per_gate, minutes=20, dt=0.2, seed=7, jam=6.0,
        k_rep=0.75, w_rep=0.45, max_agents=3000, verbose=False):
    rng = np.random.default_rng(seed)
    W,H,CELL = 120.0,100.0,2.0
    COLS,ROWS = int(W/CELL), int(H/CELL)
    GATE_L, GATE_R = np.array([34.,3.]), np.array([86.,3.])
    FUNNEL=np.array([60.,46.]); EXIT=np.array([60.,56.]); SANGAM=np.array([60.,90.])
    VS=1.35
    px=np.zeros(0);py=np.zeros(0);pv=np.zeros(0);ps=np.zeros(0);pw=np.zeros(0);pl=np.zeros(0)
    t=0.;acc=0.;dens=np.zeros((ROWS,COLS));track=[]
    def d_of(x,y):
        c=np.clip((x/CELL).astype(int),0,COLS-1); r=np.clip((y/CELL).astype(int),0,ROWS-1)
        return dens[r,c]
    def recompute():
        nonlocal dens
        c=np.clip((px/CELL).astype(int),0,COLS-1); r=np.clip((py/CELL).astype(int),0,ROWS-1)
        flat=np.bincount(r*COLS+c,minlength=ROWS*COLS).astype(float)
        dens=(flat/(CELL*CELL)).reshape(ROWS,COLS)

    while t < minutes*60:
        acc+=dt*spawn_per_gate*2; n=int(acc)
        if n:
            acc-=n
            if len(px)+n<=max_agents:
                g=rng.random(n)<0.5
                gx=np.where(g,GATE_L[0],GATE_R[0]); gy=np.where(g,GATE_L[1],GATE_R[1])
                px=np.concatenate([px,gx+(rng.random(n)-.5)*14]);py=np.concatenate([py,gy+(rng.random(n)-.5)*4])
                pv=np.concatenate([pv,VS*(.85+rng.random(n)*.3)]);ps=np.concatenate([ps,np.zeros(n)])
                pw=np.concatenate([pw,rng.random(n)*2*np.pi])
                pl=np.concatenate([pl,(rng.random(n)-.5)*gap_w*0.92])
        if len(px):
            tx=np.full(len(px),SANGAM[0]);ty=np.full(len(py),SANGAM[1])
            m1=py<FUNNEL[1];tx[m1]=FUNNEL[0]+pl[m1];ty[m1]=FUNNEL[1]
            m2=(~m1)&(py<EXIT[1]);tx[m2]=EXIT[0]+pl[m2];ty[m2]=EXIT[1]
            m3=py>=EXIT[1];tx[m3]=SANGAM[0]+pl[m3]
            dx=tx-px;dy=ty-py;dist=np.hypot(dx,dy);dist[dist==0]=1
            dx/=dist;dy/=dist

            # ---- PRESSURE: push away from dense neighbours ----
            rx=-(d_of(px+1.5,py)-d_of(px-1.5,py))
            ry=-(d_of(px,py+1.5)-d_of(px,py-1.5))
            rmag=np.hypot(rx,ry)
            sc=np.minimum(1.0,rmag*k_rep)/np.maximum(rmag,1e-9)
            rx*=sc;ry*=sc
            vx=dx*(1-w_rep)+rx*w_rep; vy=dy*(1-w_rep)+ry*w_rep
            vn=np.hypot(vx,vy);vn[vn==0]=1
            vx/=vn;vy/=vn

            pw+=dt*1.6;wob=np.sin(pw)*.22
            ahead=d_of(px,py)*.4+d_of(px+dx*3,py+dy*3)*.6
            cong=np.clip(ahead/jam,0,1)
            ts=pv*(1-cong)
            ps+=(ts-ps)*min(1,dt*4)
            px+=(vx+wob*-vy)*ps*dt;py+=(vy+wob*vx)*ps*dt
            px=np.clip(px,1,W-1);py=np.clip(py,1,H-1)
            k=py<=87
            px,py,pv,ps,pw,pl=px[k],py[k],pv[k],ps[k],pw[k],pl[k]
        t+=dt
        recompute()
        if abs(t%30)<dt:
            pk=dens.max();r,c=np.unravel_index(dens.argmax(),dens.shape)
            track.append((t,len(px),pk,c*CELL+1,r*CELL+1))
    mc=gap_w/2
    if not track: return
    mx=max(p[2] for p in track)
    cross=next((p[0] for p in track if p[2]>=5),None)
    choke=sum(1 for p in track if 60-mc<=p[3]<=60+mc and 42<=p[4]<=58)
    tail=np.mean([p[2] for p in track[-10:]])
    print(f"{gap_w:5d} {spawn_per_gate:8d} | {mx:6.2f} {tail:7.2f} {str(int(cross) if cross else '-'):>7} {track[-1][1]:8d}  {choke}/{len(track)}")
    if verbose:
        for p in track[::4]: print(f"      t={p[0]:5.0f}  N={p[1]:5d}  peak={p[2]:5.2f} at ({p[3]:.0f},{p[4]:.0f})")

print(f"{'gap':>5} {'spawn/s':>8} | {'peak':>6} {'tail':>7} {'1st>5':>7} {'finalN':>8}  choke-loc")
print("-"*64)
for gap,sp in [(8,10),(8,14),(10,14),(12,14),(16,20),(16,30),(8,20)]:
    run(gap,sp)
print("\nDetail for gap=8, spawn=14:")
run(8,14,verbose=True)
