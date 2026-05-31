"use client";

interface Props {
  title: string;
  price: string;
  features: string[];
  active: boolean;
  onSelect: () => void;
}

export default function PricingCard({ title, price, features, active, onSelect }: Props) {
  return (
    <div
      className={`rounded-xl p-4 border ${
        active ? "border-purple-500 bg-purple-900/30" : "border-gray-800 bg-gray-900"
      }`}
    >
      <h3 className="text-lg font-bold">{title}</h3>
      <p className="text-2xl font-bold my-2">{price}</p>
      <ul className="text-sm space-y-1 mb-4">
        {features.map((f, i) => (
          <li key={i} className="text-gray-400 flex items-center gap-1">
            <span className="text-green-400">&check;</span> {f}
          </li>
        ))}
      </ul>
      <button
        onClick={onSelect}
        disabled={active}
        className={`w-full py-2 rounded-lg text-sm font-medium ${
          active
            ? "bg-purple-700 text-white cursor-default"
            : "bg-purple-600 hover:bg-purple-500 text-white"
        }`}
      >
        {active ? "Current Plan" : "Upgrade"}
      </button>
    </div>
  );
}
