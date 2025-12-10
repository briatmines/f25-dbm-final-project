const cnv = document.querySelector('#cnv');

const P_BG_CLR     = "#bae7f9";
const P_ITEM_CLR   = "#6346e2";
const P_TAG_CLR    = "#53e246";
const P_RECIPE_CLR = "#e24646";

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
    // background
    ctx.fillStyle = P_BG_CLR;
    ctx.fillRect(0, 0, W, H);

    function q_interpolate(t, {x: x1, y: y1}, {x: x2, y: y2}, {x: x3, y: y3}) {
        const a = 1 - 3 * t + 2 * t * t;
        const b = 4 * t - 4 * t * t;
        const c = -t + 2 * t * t;
        return {
            x: a * x1 + b * x2 + c * x3,
            y: a * y1 + b * y2 + c * y3,
        };
    }

    // draw recipes
    ctx.strokeStyle = "black";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const [id, {ingredients, result: {id: result_id, count: result_count}}] of recipes) {
        const ingredient_stack = new Map();
        for (const {position, item, tag} of ingredients) {
            const id = item != null ? `item{${item}}` : `tag{${tag}}`;
            ingredient_stack.set(
                id,
                (ingredient_stack.get(id) ?? 0) + 1
            );
        }

        const {x: recipe_x, y: recipe_y} = orbs.get(`recipe{${id}}`);
        const {x: result_x, y: result_y} = orbs.get(`item{${result_id}}`);

        for (const [ingredient_id, count] of ingredient_stack) {
            const {x: ix, y: iy} = orbs.get(ingredient_id);

            ctx.lineWidth = count * R / 10;
            ctx.beginPath();
            ctx.moveTo((ix + 0.5) * W / 2, (iy + 0.5) * H / 2);
            for (let t = 0; t <= 0.5; t += 0.5 / 16) {
                const {x, y} = q_interpolate(
                    t,
                    {x: ix, y: iy},
                    {x: recipe_x, y: recipe_y},
                    {x: result_x, y: result_y},
                );
                ctx.lineTo((x + 0.5) * W / 2, (y + 0.5) * H / 2);
            }
            ctx.stroke();
        }

        let ingredient_mean_x = 0;
        let ingredient_mean_y = 0;
        let ingredient_count = 0;
        for (const [ingredient_id, count] of ingredient_stack) {
            const {x, y} = orbs.get(ingredient_id);
            ingredient_mean_x += x * count;
            ingredient_mean_y += y * count;
            ingredient_count += count;
        }
        ingredient_mean_x /= ingredient_count;
        ingredient_mean_y /= ingredient_count;

        let dx = recipe_x;
        let dy = recipe_y;
        let d  = Infinity;

        ctx.lineWidth = result_count * R / 10;
        ctx.beginPath();
        ctx.moveTo(
            (recipe_x + 0.5) * W / 2,
            (recipe_y + 0.5) * H / 2
        );
        for (let t = 0.5; t <= 1; t += 0.5 / 16) {
            const {x, y} = q_interpolate(
                t,
                {x: ingredient_mean_x, y: ingredient_mean_y},
                {x: recipe_x, y: recipe_y},
                {x: result_x, y: result_y},
            );
            ctx.lineTo((x + 0.5) * W / 2, (y + 0.5) * H / 2);

            const p_dx = (x - recipe_x) * W / 2;
            const p_dy = (y - recipe_y) * H / 2;
            const p_d  = Math.abs(Math.hypot(p_dx, p_dy) - 4 * R);
            if (p_d < d) {
                dx = p_dx;
                dy = p_dy;
                d  = p_d;
            }
        }
        ctx.stroke();

        orbs.get(`recipe{${id}}`).alpha = Math.atan2(dy, dx);
    }

    // draw tags
    ctx.strokeStyle = "black";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = 3 * R / 5;
    ctx.setLineDash([4 * R, 2 * R]);
    for (const [tag, {items}] of tags) {
        const {x: tx, y: ty} = orbs.get(`tag{${tag}}`);
        for (const item of items) {
            const {x: ix, y: iy} = orbs.get(`item{${item}}`);

            ctx.beginPath();
            ctx.moveTo((ix + 0.5) * W / 2, (iy + 0.5) * H / 2);
            ctx.lineTo((tx + 0.5) * W / 2, (ty + 0.5) * H / 2);
            ctx.stroke();
        }
    }

    // draw orbs
    ctx.fillStyle   = "white";
    ctx.strokeStyle = "black";
    ctx.lineWidth = R;
    ctx.setLineDash([]);
    for (const [id, {type, x, y, alpha}] of orbs) {
        const adj_x = (x + 0.5) * W / 2;
        const adj_y = (y + 0.5) * H / 2;

        ctx.beginPath();
        switch (type) {
            case 'recipe': {
                // console.log(alpha);
                ctx.fillStyle = P_RECIPE_CLR;
                ctx.moveTo(
                    adj_x + 2 * R * Math.cos(alpha - TAU / 6),
                    adj_y + 2 * R * Math.sin(alpha - TAU / 6)
                );
                ctx.ellipse(
                    adj_x, adj_y,
                    2 * R, 2 * R,
                    0,
                    alpha - TAU / 6, alpha + TAU / 6,
                    true
                );
                ctx.lineTo(
                    adj_x + 4 * R * Math.cos(alpha),
                    adj_y + 4 * R * Math.sin(alpha)
                );
                ctx.closePath();
            }; break;
            case 'item': {
                ctx.fillStyle = P_ITEM_CLR;
                ctx.ellipse(
                    adj_x, adj_y,
                    2 * R, 2 * R,
                    0,
                    0, TAU
                );
            }; break;
            case 'tag': {
                ctx.fillStyle = P_TAG_CLR;
                ctx.moveTo(adj_x + 3 * R, adj_y        );
                ctx.lineTo(adj_x,         adj_y + 3 * R);
                ctx.lineTo(adj_x - 3 * R, adj_y        );
                ctx.lineTo(adj_x,         adj_y - 3 * R);
                ctx.closePath();
            }; break;
        }
        ctx.stroke();
        ctx.fill();
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

let mouse_x = 0;
let mouse_y = 0;

cnv.addEventListener("mousemove", (e) => {
    mouse_x = e.offsetX * 2 / W - 0.5;
    mouse_y = e.offsetY * 2 / H - 0.5;
});
