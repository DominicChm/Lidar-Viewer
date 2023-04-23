<script lang="ts">
    import { onMount } from "svelte";
    import { io, Socket } from "socket.io-client";

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

        connectingSock.on("scan", console.log);

        return () => {
            sock.close();
        };
    });
</script>

{#if sock && scan}
    <svg>
        {#each scan.points as {strength, distance, invalid, warn}, i (i)}
        <g></g>
        {/each}
    </svg>
{/if}
