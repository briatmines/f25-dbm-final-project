const cnv = document.querySelector('#cnv');

const W = cnv.width;
const H = cnv.height;
const R = 5;
const K = 0.00001;
const MU = 0.001;
const Q = 0.00000001;
const G = Q * 1000;
const TAU = 2 * Math.PI;

const ctx = cnv.getContext('2d');

const recipes_json = await (await fetch("recipe.json")).json();
const tags_json    = await (await fetch("tag.json")).json();
const items_json   = await (await fetch("item.json")).json();

const recipes = new Map(recipes_json.map(({id,  ...ps}) => [id,  ps]));
const tags    = new Map(tags_json.map(   ({tag, ...ps}) => [tag, ps]));
const items   = new Set(items_json);

let orbs = new Map([].concat(
    recipes_json.map(({id})  => [`recipe{${id}}`, 'recipe']),
    tags_json   .map(({tag}) => [`tag{${tag}}`,   'tag'   ]),
    items_json  .map(item    => [`item{${item}}`, 'item'  ]),
).map(([id, type]) => [id, {
    type,
    x:  Math.random(),
    y:  Math.random(),
    vx: (Math.random() - 0.5) * 0.0015,
    vy: (Math.random() - 0.5) * 0.0015,
    ax: 0,
    ay: 0,
}]));

let springs = new Set();
for (const [tag, {items}] of tags) {
    for (const item of items) {
        springs.add({
            type:  'tag_item',
            start: `item{${item}}`,
            end:   `tag{${tag}}`,
        });
    }
}
for (const [id, {ingredients, result}] of recipes) {
    for (const {position, item, tag} of ingredients) {
        if (item != null) {
            springs.add({
                type:  "ingredient",
                start: `item{${item}}`,
                end:   `recipe{${id}}`,
            });
        } else {
            springs.add({
                type:  "ingredient",
                start: `tag{${tag}}`,
                end:   `recipe{${id}}`,
            });
        }
    }

    const {id: result_id, count: result_count} = result;
    springs.add({
        type:  "result",
        start: `recipe{${id}}`,
        end:   `item{${result_id}}`,
        result_count,
    });
}

function draw_frame(delta_t) {
    // background white
    ctx.fillStyle = "skyblue";
    ctx.fillRect(0, 0, W, H);

    // draw springs
    ctx.strokeStyle = "black";
    ctx.lineWidth = R / 5;
    ctx.lineCap = "round";
    for (const {type, start, end} of springs) {
        const {x: sx, y: sy} = orbs.get(start);
        const {x: ex, y: ey} = orbs.get(end);
        ctx.beginPath();
        ctx.moveTo((sx + 0.5) * W / 2, (sy + 0.5) * H / 2);
        ctx.lineTo((ex + 0.5) * W / 2, (ey + 0.5) * H / 2);
        ctx.stroke();
    }

    // draw orbs
    ctx.fillStyle = "black";
    for (const [id, {type, x, y}] of orbs) {
        ctx.beginPath();
        ctx.ellipse((x + 0.5) * W / 2, (y + 0.5) * H / 2, R, R, 0, 0, TAU);
        switch (type) {
            case 'recipe': ctx.fillStyle = "red"; break;
            case 'tag':    ctx.fillStyle = "green"; break;
            case 'item':   ctx.fillStyle = "blue"; break;
        }
        ctx.fill();
    }

    sim(delta_t);
}

function sim(delta_t) {
    // orb-local-accelerations
    const orb_arr = Array.from(orbs.values());
    for (const orb of orbs.values()) {
        orb.ax = 0;
        orb.ay = 0;

        orb.ax -= MU * orb.vx;
        orb.ay -= MU * orb.vy;

        for (let i = 0; i < 100; ++i) {
            const repel_orb = orb_arr[Math.floor(orb_arr.length * Math.random())];
            const dx = orb.x - repel_orb.x;
            const dy = orb.y - repel_orb.y;
            const d2 = dx * dx + dy * dy;
            
            if (d2 < 1E-8) continue;
            
            if (Number.isNaN(dx) || Number.isNaN(dy) || Number.isNaN(d2) || d2 == 0) {
                console.log(orb_arr, repel_orb);
                console.log(dx, dy, d2);
                throw 1;
            }

            orb.ax += Q * dx / d2;
            orb.ay += Q * dy / d2;
        }

        const dcx = orb.x - 0.5;
        const dcy = orb.y - 0.5;
        const dc2 = dcx * dcx + dcy * dcy;
        orb.ax -= G * dcx * dc2;
        orb.ay -= G * dcy * dc2;
    }

    // sproings
    for (const {start, end} of springs) {
        const start_orb = orbs.get(start);
        const end_orb   = orbs.get(end);

        const {x: sx, y: sy} = start_orb;
        const {x: ex, y: ey} = end_orb;

        start_orb.ax += K * (ex - sx);
        start_orb.ay += K * (ey - sy);

        end_orb.ax += K * (sx - ex);
        end_orb.ay += K * (sy - ey);
    }

    // update orbs
    for (const orb of orbs.values()) {
        orb.vx += orb.ax;
        orb.vy += orb.ay;

        orb.x += orb.vx;
        orb.y += orb.vy;
    }
}

let prev_t;

function draw_loop(t) {
    if (prev_t != null) {
        draw_frame(t - prev_t);
    }
    
    prev_t = t;
    requestAnimationFrame(draw_loop);
}

draw_loop(0);
