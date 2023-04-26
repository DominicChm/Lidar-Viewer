<script lang="ts">
    import { onMount } from "svelte";
    import { io, Socket } from "socket.io-client";

    const radius = 6000; //mm
    let sock: Socket;
    let scan: {
        rpm: number;
        points: number[];
    };

    let annotations: {
        highlights: number[];
        lines: [number, number, number, number][];
        points: [number, number][];
    };

    // https://socket.io/docs/v4/client-initialization/
    onMount(() => {
        let connectingSock = io("/lidar", { path: "/api" });
        connectingSock.on("connect", () => {
            sock = connectingSock;
        });

        connectingSock.on("scan", (newScan) => (scan = newScan));
        connectingSock.on("annotations", (newan) => (annotations = newan));

        return () => {
            sock.close();
        };
    });
</script>

{#if sock}
    connected
    <svg
        viewBox={`${-radius} ${-radius} ${2 * radius} ${2 * radius}`}
        class="w-full aspect-square object-contain bg-green-500 -scale-y-100"
    >
        <circle cx="0" cy="0" r="1%" fill="red" />
        {#if scan}
            <g>
                {#each scan.points as distance, i (i)}
                    {@const angle = -(i * Math.PI) / 180}
                    {@const x = Math.cos(angle) * distance}
                    {@const y = Math.sin(angle) * distance}

                    <circle cx={x} cy={y} r=".25%" />
                    {#if annotations && annotations.highlights.includes(Math.abs(angle))}
                        <line x1={0} y1={0} x2={x} y2={y} stroke="blue" stroke-width=".25%"></line>
                    {/if}
                {/each}
            </g>
        {/if}

        {#if annotations}
            <g>
                {#each annotations.lines as line, i (i)}
                    {@const [x1, y1, x2, y2] = line}

                    <line
                        {x1}
                        {y1}
                        {x2}
                        {y2}
                        stroke="black"
                        stroke-width=".2%"
                    />
                {/each}

                {#each annotations.points as point, i (i)}
                    {@const [x, y] = point}

                    <circle {x} {y} r=".25%" fill="blue"/>
                {/each}
            </g>
        {/if}
    </svg>
{/if}
