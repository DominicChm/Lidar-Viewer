<script lang="ts">
    import { onMount } from "svelte";
    import { io, Socket } from "socket.io-client";

    const radius = 6000; //mm
    let sock: Socket;
    let scan: {
        rpm: number;
        points: {
            strength: number;
            distance: number;
            invalid: boolean;
            warn: boolean;
        }[];
    };

    // https://socket.io/docs/v4/client-initialization/
    onMount(() => {
        let connectingSock = io("/lidar", { path: "/api" });
        connectingSock.on("connect", () => {
            sock = connectingSock;
        });

        connectingSock.on("scan", (newScan) => (scan = newScan));

        return () => {
            sock.close();
        };
    });
</script>

{#if sock && scan}
    connected
    <svg
        viewBox={`${-radius} ${-radius} ${2 * radius} ${2 * radius}`}
        class="w-full aspect-square object-contain bg-green-500"
    >
        <circle cx="0" cy="0" r="1%" fill="red" />

        <g>
            {#each scan.points as { strength, distance, invalid, warn }, i (i)}
                {@const angle = (i * Math.PI) / 180}
                {@const x = Math.cos(angle) * distance}
                {@const y = Math.sin(angle) * distance}

                <circle cx={x} cy={y} r=".25%" />
            {/each}
        </g>
    </svg>
{/if}
