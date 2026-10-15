"""Design the DEMO SCENARIO.
Problem: crowd reaches plateau (~6.8 p/m2) and sits -> nothing to predict ->
warning chatters "0 min, 1 min, 2 min".
A real event has a SHAPE: quiet -> building -> SURGE -> peak -> disperse.
We want a baseline that is BUSY BUT SAFE (~4 p/m2), and a surge that pushes
the choke point over 5.0 so the forecast has a genuine job to do.
"""
import numpy as np

def run(baseline, surge_mult, surge_at, surge_dur, minutes=22, dt=0.2,
        seed=7, jam=6.8, k_rep=0.75, w_rep=0.45, max_agents=3000):
    rng = np.random.default_rng(seed)
    W,H,CELL = 120.0,100.0,2.0
    COLS,ROWS = int(W/CELL), int(H/CELL)
    GATE_L,GATE_R = np.array([34.,3.]), np.array([86.,3.])
    FUNNEL=np.array([60.,46.]); EXIT=np.array([60.,56.]); SANGAM=np.array([60.,90.])
    GAP_L,GAP_R = 54.,66.; VS=1.35
    px=np.zeros(0);py=np.zeros(0);pv=np.zeros(0);ps=np.zeros(0);pw=np.zeros(0);pl=np.zeros(0)
    t=0.;acc=0.;dens=np.zeros((ROWS,COLS));log=[]
    def d_of(x,y):
        c=np.clip((x/CELL).astype(int),0,COLS-1);r=np.clip((y/CELL).astype(int),0,ROWS-1)
        return dens[r,c]
    def recompute():
        nonlocal dens
        c=np.clip((px/CELL).astype(int),0,COLS-1);r=np.clip((py/CELL).astype(int),0,ROWS-1)
        flat=np.bincount(r*COLS+c,minlength=ROWS*COLS).astype(float)
        dens=(flat/(CELL*CELL)).reshape(ROWS,COLS)
    while t<minutes*60:
        rate = baseline*(surge_mult if surge_at<=t<surge_at+surge_dur else 1.0)
        acc+=dt*rate*2; n=int(acc)
        if n:
            acc-=n
            if len(px)+n<=max_agents:
                g=rng.random(n)<0.5
                gx=np.where(g,GATE_L[0],GATE_R[0]);gy=np.where(g,GATE_L[1],GATE_R[1])
                px=np.concatenate([px,gx+(rng.random(n)-.5)*14]);py=np.concatenate([py,gy+(rng.random(n)-.5)*4])
                pv=np.concatenate([pv,VS*(.85+rng.random(n)*.3)]);ps=np.concatenate([ps,np.zeros(n)])
                pw=np.concatenate([pw,rng.random(n)*2*np.pi])
                pl=np.concatenate([pl,(rng.random(n)-.5)*((GAP_R-GAP_L)*0.92)])
        if len(px):
            tx=np.full(len(px),SANGAM[0]);ty=np.full(len(py),SANGAM[1])
            m1=py<FUNNEL[1];tx[m1]=FUNNEL[0]+pl[m1];ty[m1]=FUNNEL[1]
            m2=(~m1)&(py<EXIT[1]);tx[m2]=EXIT[0]+pl[m2];ty[m2]=EXIT[1]
            m3=py>=EXIT[1];tx[m3]=SANGAM[0]+pl[m3]
            dx=tx-px;dy=ty-py;dist=np.hypot(dx,dy);dist[dist==0]=1
            dx/=dist;dy/=dist
            rx=-(d_of(px+1.5,py)-d_of(px-1.5,py));ry=-(d_of(px,py+1.5)-d_of(px,py-1.5))
            rm=np.hypot(rx,ry);sc=np.minimum(1.0,rm*k_rep)/np.maximum(rm,1e-9)
            rx*=sc;ry*=sc
            vx=dx*(1-w_rep)+rx*w_rep;vy=dy*(1-w_rep)+ry*w_rep
            vn=np.hypot(vx,vy);vn[vn==0]=1;vx/=vn;vy/=vn
            pw+=dt*1.6;wob=np.sin(pw)*.22
            ahead=d_of(px,py)*.4+d_of(px+dx*3,py+dy*3)*.6
            cong=np.clip(ahead/jam,0,1)
            ts=pv*(1-cong)
            ps+=(ts-ps)*min(1,dt*4)
            px+=(vx+wob*-vy)*ps*dt;py+=(vy+wob*vx)*ps*dt
            px=np.clip(px,1,W-1);py=np.clip(py,1,H-1)
            k=py<=87
            px,py,pv,ps,pw,pl=px[k],py[k],pv[k],ps[k],pw[k],pl[k]
        t+=dt; recompute()
        if abs(t%15)<dt:
            pk=dens.max();r,c=np.unravel_index(dens.argmax(),dens.shape)
            log.append((t,pk,c*CELL+1,r*CELL+1,len(px)))
    return log

print("STEP 1 - baseline spawn vs steady-state peak density")
print(f"{'baseline':>9} | {'peak (warmed up)':>17}")
print("-"*30)
for b in [4,6,8,10,12]:
    log = run(b, 1.0, 99999, 0, minutes=12)
    tail = np.mean([p[1] for p in log[-12:]])
    print(f"{b:9d} | {tail:17.2f}")

print()
print("STEP 2 - surge (baseline=8, surge starts t=6min, lasts 60s)")
print(f"{'mult':>5} | {'peak':>6} {'first>5':>8} {'secs above 5':>13}")
print("-"*42)
for mult in [1.8,2.2,2.6,3.0]:
    log = run(8, mult, 360, 60, minutes=18)
    pk = max(p[1] for p in log)
    above = [p[0] for p in log if p[1]>=5.0]
    dur = (max(above)-min(above)) if above else 0
    first = min(above) if above else None
    print(f"{mult:5.1f} | {pk:6.2f} {str(int(first) if first else '-'):>8} {dur:13.0f}")
