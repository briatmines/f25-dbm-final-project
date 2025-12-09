const cnv = document.querySelector('#cnv');

const W = cnv.width;
const H = cnv.height;
const R = 5;
const K = 0.0002;
const Q = 0.00000001;
const G = 0.00001;
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

    // hovered orb highlight
    let closest_orb;
    let closest_orb_dist_sq = Infinity;
    for (const [id, {x, y}] of orbs) {
        const dx = mouse_x - x;
        const dy = mouse_y - y;
        const d2 = dx * dx + dy * dy;
        if (d2 < closest_orb_dist_sq) {
            closest_orb = id;
            closest_orb_dist_sq = d2;
        }
    }

    ctx.fillStyle = "white";
    if (closest_orb_dist_sq <= 0.001) {
        const {x, y} = orbs.get(closest_orb);
        ctx.beginPath();
        ctx.ellipse(
            (x + 0.5) * W / 2, (y + 0.5) * H / 2,
            1.5 * R, 1.5 * R,
            0,
            0, TAU);
        ctx.fill();
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

let elapsed_t = 0;
function sim(delta_t) {
    elapsed_t += delta_t;
    // ramp friction over time
    const MU = Math.min(0.00083 * Math.exp(0.000059 * elapsed_t), 1);

    // orb-local-accelerations
    const orb_arr = Array.from(orbs.values());
    for (const orb of orbs.values()) {
        orb.ax = 0;
        orb.ay = 0;

        // friction
        orb.ax -= MU * orb.vx;
        orb.ay -= MU * orb.vy;

        // random acts of repulsion
        for (let i = 0; i < 200; ++i) {
            const repel_orb = orb_arr[Math.floor(orb_arr.length * Math.random())];
            repel(orb, repel_orb);
        }

        // "gravity"
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

        sproing(start_orb, end_orb);
    }

    // update orbs
    for (const orb of orbs.values()) {
        orb.vx += orb.ax;
        orb.vy += orb.ay;

        orb.x += orb.vx;
        orb.y += orb.vy;
    }

    let max_v_sq = -Infinity;
    for (const {vx, vy} of orbs.values()) {
        const v_sq = vx * vx + vy * vy;
        if (max_v_sq < v_sq) max_v_sq = v_sq;
    }
    if (max_v_sq < 1E-7) {
        pretty_pass();
        throw "Stop looping"; // this is silly, but works
    }
}

function repel(orb1, orb2) {
    const dx = orb1.x - orb2.x;
    const dy = orb1.y - orb2.y;
    const d3 = Math.hypot(dx, dy) ** 3;

    if (d3 < 1E-8) return;

    const rax = Q * dx / d3;
    const ray = Q * dy / d3;

    orb1.ax += rax;
    orb1.ay += ray;
    orb2.ax -= rax;
    orb2.ay -= ray;
}

function sproing(start_orb, end_orb) {
    const {x: sx, y: sy} = start_orb;
    const {x: ex, y: ey} = end_orb;

    start_orb.ax += K * (ex - sx);
    start_orb.ay += K * (ey - sy);

    end_orb.ax += K * (sx - ex);
    end_orb.ay += K * (sy - ey);

    repel(start_orb, end_orb);
}

function pretty_pass() {
    // TODO
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

let mouse_x = 0;
let mouse_y = 0;

cnv.addEventListener("mousemove", (e) => {
    mouse_x = e.offsetX * 2 / W - 0.5;
    mouse_y = e.offsetY * 2 / H - 0.5;
});
