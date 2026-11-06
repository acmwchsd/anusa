<!-- Settings shared by everyone using this server. -->
<script lang="ts">
	import SidePanel from '#lib/components/SidePanel.svelte';
	import { liveConnection } from '#lib/live-connection.svelte.ts';

	const formatPercent = (value: number) => `${Math.round(value * 100)}%`;
	const formatSeconds = (value: number) => `${value}s`;

	const SETTING_SLIDERS = [
		{
			settingName: 'match_threshold',
			label: 'Match strictness',
			minimum: 0.3,
			maximum: 0.7,
			step: 0.01,
			formatValue: formatPercent,
			hint: 'Lower names more faces but risks mix-ups. 45% suits most classes.'
		},
		{
			settingName: 'keyword_sensitivity',
			label: 'Keyword sensitivity',
			minimum: 0.6,
			maximum: 1,
			step: 0.01,
			formatValue: formatPercent,
			hint: 'How closely speech must match a trigger phrase (100% = exact).'
		},
		{
			settingName: 'cooldown_s',
			label: 'Pause between voice photos',
			minimum: 0,
			maximum: 15,
			step: 1,
			formatValue: formatSeconds,
			hint: 'Stops one shout from taking several photos.'
		}
	] as const;
</script>

{#if liveConnection.settings}
	{@const settings = liveConnection.settings}
	<SidePanel title="Recognition" collapsible>
		{#each SETTING_SLIDERS as slider (slider.settingName)}
			{@const currentValue = settings[slider.settingName]}
			<label class="slider">
				<span class="value">{slider.label} <strong>{slider.formatValue(currentValue)}</strong></span>
				<input
					type="range"
					min={slider.minimum}
					max={slider.maximum}
					step={slider.step}
					value={currentValue}
					style:--fill="{((currentValue - slider.minimum) / (slider.maximum - slider.minimum)) * 100}%"
					oninput={(event) => liveConnection.updateSettings({ [slider.settingName]: +event.currentTarget.value })}
				/>
				<span class="faint small">{slider.hint}</span>
			</label>
		{/each}
	</SidePanel>
{/if}

<style>
	.slider {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin-bottom: 12px;
	}
	.value {
		display: flex;
		justify-content: space-between;
	}
	.value strong {
		font-family: var(--font-data);
		font-weight: 400;
		color: var(--accent);
	}
</style>
